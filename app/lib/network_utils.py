import asyncio
import logging
from datetime import datetime, timedelta

from app.config.network_configuration import get_relay_chain_rpc_url, network_sudo_seed, derivation_root_seed, \
    node_http_endpoint, get_network, relay_chain_consensus, node_ws_endpoint
from app.lib.balance_utils import fund_accounts
from app.lib.collator_account import get_derived_moon_collator_account, get_derived_collator_account, \
    get_derived_collator_session_keys
from app.lib.collator_manager import get_collator_status, \
    collator_register, collator_deregister, get_moon_collator_status, \
    set_collator_selection_invulnerables, get_collator_selection_invulnerables
from app.lib.collator_mint import collator_set_keys
from app.lib.kubernetes_client import list_validator_pods, get_external_validators_from_configmap, \
    list_collator_pods, get_pod, list_substrate_node_pods
from app.lib.node_utils import is_node_ready, \
    get_last_runtime_upgrade, has_pod_node_role_label, \
    check_has_session_keys
from app.lib.parachain_manager import get_parachain_id, get_all_parachain_lifecycles, \
    initialize_parachain, cleanup_parachain, get_chain_wasm, get_parachain_head, get_parathreads_ids, \
    get_parachains_ids, get_all_parachain_leases_count, get_all_parachain_current_code_hashes, \
    get_permanent_slot_lease_period_length, get_all_parachain_heads, get_parachain_node_client
from app.lib.session_keys import rotate_node_session_keys, set_node_session_key, get_queued_keys
from app.lib.stash_accounts import get_derived_node_stash_account_address, get_node_stash_account_mnemonic, \
    get_account_funds
from app.lib.substrate import get_relay_chain_client, get_node_client, substrate_rpc_request
from app.lib.validator_manager import get_validator_set, get_validators_pending_addition, \
    get_validators_pending_deletion, \
    deregister_validators, register_validators, setup_pos_validator, staking_chill, get_account_session_keys, \
    get_derived_validator_session_keys

log = logging.getLogger(__name__)

relay_chain_network_name = get_network()


def get_validator_account_from_pod(pod):
    node_name = pod.metadata.name
    validator_account = pod.metadata.labels.get('validatorAccount', None)
    if validator_account:
        return validator_account
    else:
        return get_derived_node_stash_account_address(derivation_root_seed(), node_name)


def get_collator_account_from_pod(pod):
    node_name = pod.metadata.name
    collator_account = pod.metadata.labels.get('collatorAccount', None)
    print(collator_account)
    if collator_account:
        return collator_account
    else:
        chain = pod.metadata.labels['chain']
        if chain.startswith("moon"):
            return get_derived_moon_collator_account(node_name)
        else:
            # 42 is the ss58 format default value, see https://polkadot.js.org/docs/keyring/start/ss58/
            ss58_format = pod.metadata.labels.get('ss58Format','42')
            return get_derived_collator_account(node_name, ss58_format)


def get_validator_status(node_stash_account_address, validator_set, validators_to_add, validators_to_retire):
    if node_stash_account_address in validators_to_add:
        validator_status = 'pending_addition'
    elif node_stash_account_address in validators_to_retire:
        validator_status = 'pending_deletion'
    else:
        validator_status = node_stash_account_address in validator_set
    return validator_status


def list_validators(stateful_set_name=''):
    ws_endpoint = get_relay_chain_rpc_url()
    external_validators = get_external_validators_from_configmap()
    validator_pods = list_validator_pods(stateful_set_name)
    validator_set = get_validator_set(ws_endpoint)
    validators_to_add = get_validators_pending_addition(ws_endpoint)
    validators_to_retire = get_validators_pending_deletion(ws_endpoint)
    validators = []

    # Add missing validators to the list (only when not filtering on a statefulset)
    if not stateful_set_name:
        for node_name, node_address in external_validators.items():
            is_validator = get_validator_status(node_address, validator_set, validators_to_add,
                                                        validators_to_retire)
            if is_validator:
                validators.append({'name': node_name, 'location': 'external', 'address': node_address,
                                   # 'funds': node_stash_account_funds,
                                   'is_validator': is_validator, 'status': '?', 'version': '?'})

    for pod in validator_pods:
        node_stash_account_address = get_validator_account_from_pod(pod)
        is_validator = get_validator_status(node_stash_account_address, validator_set, validators_to_add,
                                                    validators_to_retire)
        validators.append({'name': pod.metadata.name, 'location': 'in_cluster',
                           'address': node_stash_account_address,
                           # 'funds': node_stash_account_funds,
                           'is_validator': is_validator,
                           'status': pod.status.phase,
                           'version': pod.spec.containers[0].image})

    # Add missing validators to the list (only when not filtering on a statefulset)
    if not stateful_set_name:
        # Find validator addresses which are neither in configmap nor Kubernetes pod
        known_validators_addresses = []
        for validator in validators:
            if validator['is_validator']:
                known_validators_addresses.append(validator['address'])
        i = 0
        for validator_address in validator_set:
            if not validator_address in known_validators_addresses:
                is_validator = get_validator_status(validator_address, validator_set, validators_to_add,
                                                            validators_to_retire)
                validators.append(
                    {'name': 'unknown-validator-' + str(i), 'location': 'unknown',
                     'address': validator_address,
                     # 'funds': node_stash_account_funds,
                     'is_validator': is_validator, 'status': 'Missing', 'version': '?'})
                i = i + 1
    return validators


def get_node_info_from_pod(pod):
    node_name = pod.metadata.name
    node_labels = pod.metadata.labels
    node_chain = node_labels.get('chain')
    node_ss58_format = node_labels.get('ss58Format', '42')
    node_role = node_labels.get('role')
    node_para_id = node_labels.get('paraId')
    node_status = pod.status.phase
    if pod.status.start_time:
        node_uptime = str(timedelta(seconds=int(datetime.now().timestamp() - pod.status.start_time.timestamp())))
    else:
        node_update = '?'
    node_image = pod.spec.containers[0].image
    node_args = pod.spec.containers[0].args

    return {
        'name': node_name,
        'labels': node_labels,
        'chain': node_chain,
        'ss58_format': node_ss58_format,
        'role': node_role,
        'para_id': node_para_id,
        'status': node_status,
        'uptime': node_uptime,
        'image': node_image,
        'args': node_args,
    }


def get_node_info_from_rpc(node_name):
    http_endpoint = node_http_endpoint(node_name)
    node_ready = is_node_ready(http_endpoint)
    if node_ready:
        node_client = get_node_client(node_name)
        node_peer_id = substrate_rpc_request(node_client, 'system_localPeerId')
        node_sync_state = substrate_rpc_request(node_client, 'system_syncState')
        node_system_health = substrate_rpc_request(node_client, 'system_health')
        node_system_local_listen_addresses = substrate_rpc_request(node_client, 'system_localListenAddresses')
        node_system_peers = substrate_rpc_request(node_client, 'system_peers')
        node_system_properties = substrate_rpc_request(node_client, 'system_properties')
        node_system_roles = substrate_rpc_request(node_client, 'system_nodeRoles')
        node_version = substrate_rpc_request(node_client, 'system_version')
    else:
        node_peer_id = '?'
        node_sync_state = '?'
        node_system_health = '?'
        node_system_local_listen_addresses = '?'
        node_system_peers = '?'
        node_system_properties = '?'
        node_system_roles = '?'
        node_version = '?'
    return {
        'health': node_system_health,
        'localListenAddresses': node_system_local_listen_addresses,
        'nodeRoles': node_system_roles,
        'peerId': node_peer_id,
        'peers': node_system_peers,
        'properties': node_system_properties,
        'ready': node_ready,
        'syncState': node_sync_state,
        'version': node_version,
    }


def list_substrate_nodes(stateful_set_name):
    pods = list_substrate_node_pods()
    if stateful_set_name:
        pods = list(
            filter(lambda pod: pod.metadata.owner_references[0].name == stateful_set_name, pods))

    nodes_pods = list(filter(has_pod_node_role_label, pods))
    nodes = []
    for pod in nodes_pods:
        node_info = get_node_info_from_pod(pod)
        nodes.append(node_info)
    return nodes


def get_substrate_node(node_name):
    pod = get_pod(node_name)
    node_info = get_node_info_from_pod(pod)
    node_info.update(get_node_info_from_rpc(node_info.get("name")))
    if node_info.get("role") == "authority":
        ws_endpoint = get_relay_chain_rpc_url()
        validator_set = get_validator_set(ws_endpoint)
        validators_to_add = get_validators_pending_addition(ws_endpoint)
        validators_to_retire = get_validators_pending_deletion(ws_endpoint)
        node_info['validator_account'] = get_validator_account_from_pod(pod)
        node_info['validator_account_funds'] = get_account_funds(ws_endpoint, node_info['validator_account'])
        node_info['validator_status'] = get_validator_status(node_info['validator_account'], validator_set, validators_to_add,
                                                            validators_to_retire)
        node_info['on_chain_session_keys'] = get_account_session_keys(ws_endpoint, node_info['validator_account'])
        if node_info['on_chain_session_keys']:
            node_info['session_keys'] = node_info['on_chain_session_keys']
        else:
            node_info['session_keys'] = get_derived_validator_session_keys(node_name)
        node_client = get_node_client(node_name)
        node_info['has_session_keys'] = check_has_session_keys(node_client, node_info['session_keys'])

    if node_info.get("role") == "collator":
        node_info['collator_account'] = get_collator_account_from_pod(pod)
        chain = pod.metadata.labels['chain']
        ws_endpoint = node_ws_endpoint(node_name)
        node_client = get_node_client(node_name)
        node_info['collator_account_funds'] = get_account_funds(ws_endpoint, node_info['collator_account'])
        node_info['on_chain_session_keys'] = get_account_session_keys(ws_endpoint, node_info['collator_account'])
        # If not present in on-chain state, get derived session keys
        if node_info['on_chain_session_keys']:
            node_info['session_keys'] = node_info['on_chain_session_keys']
        else:
            node_info['session_keys'] = get_derived_collator_session_keys(node_name)
        node_info['has_session_keys'] = check_has_session_keys(node_client, node_info['session_keys'])
        if chain.startswith("moon"):
            selected_candidates = node_client.query('ParachainStaking', 'SelectedCandidates', params=[]).value
            candidate_pool = node_client.query('ParachainStaking', 'CandidatePool', params=[]).value
            node_info['collator_status'] = get_moon_collator_status(node_info['collator_account'],
                                                                    selected_candidates,
                                                                    candidate_pool)
        else:
            try:
                invulnerables = node_client.query('CollatorSelection', 'Invulnerables', params=[]).value or []
                candidates = node_client.query('CollatorSelection', 'Candidates', params=[]).value or []
                node_info['collator_status'] = get_collator_status(node_info['collator_account'], invulnerables, candidates)
            except:
                node_info['collator_status'] = '?'
    return node_info


# Setup validator node (rotate + submit session key): returns stash address/empty string depending on success
async def setup_validators_session_keys(node_name):
    log.info("Setting up validator session key for {}".format(node_name))
    ws_endpoint = get_relay_chain_rpc_url()
    validators_root_seed = derivation_root_seed()

    # Rotate session keys
    node_endpoint = node_http_endpoint(node_name)
    node_ready = is_node_ready(node_endpoint)
    stash_account_address = get_derived_node_stash_account_address(validators_root_seed, node_name)
    if not node_ready:
        log.warning('{} is not ready, aborting rotate key operation'.format(node_name))
        return ''
    else:
        log.info("Rotating session key on {} ({}) session key".format(node_name, stash_account_address))
        node_session_key = rotate_node_session_keys(node_endpoint)
        # If rotate_key result from node is not empty, set session key and mark account to be registered
        if node_session_key:
            log.info("Setting session key for {} ({})".format(stash_account_address, node_session_key))
            node_stash_account_mnemonic = get_node_stash_account_mnemonic(validators_root_seed, node_name)
            session_key_set_status = set_node_session_key(ws_endpoint, node_stash_account_mnemonic, node_session_key)
            # Don't add the account to the validator set if the setKey operation failed
            if session_key_set_status:
                log.info('Successfully set session keys'.format(stash_account_address))
                return stash_account_address
            else:
                log.warning(
                    'failed to set session keys, removing {} from addresses to be added to the validators set'.format(
                        stash_account_address))
                return ''


def is_validator_address_already_registered(address, validator_set, validators_to_add, validators_to_retire):
    is_node_in_validator_set = address in validator_set
    is_node_in_validators_to_add = address in validators_to_add
    is_node_in_validators_to_retire = address in validators_to_retire
    return is_node_in_validator_set or is_node_in_validators_to_add or is_node_in_validators_to_retire


def register_validator_addresses(validator_addresses_to_register):
    log.info(f'registering the following validators addresses: {validator_addresses_to_register}')
    ws_endpoint = get_relay_chain_rpc_url()
    sudo_seed = network_sudo_seed()
    register_validators(ws_endpoint, sudo_seed, validator_addresses_to_register)


async def register_validator_pods(pods):
    log.info(f'registering validators pods')

    ws_endpoint = get_relay_chain_rpc_url()
    substrate_client = get_relay_chain_client()
    sudo_seed = network_sudo_seed()
    validator_set = get_validator_set(ws_endpoint)
    validators_to_add = get_validators_pending_addition(ws_endpoint)
    validators_to_retire = get_validators_pending_deletion(ws_endpoint)
    node_stash_accounts = []
    nodes_to_register = []
    consensus = relay_chain_consensus()
    validators_root_seed = derivation_root_seed()

    for pod in pods:
        node = pod.metadata.name
        log.info(f'starting to register validator: {node}')
        validator_stash_account = get_validator_account_from_pod(pod)
        if not is_validator_address_already_registered(validator_stash_account, validator_set, validators_to_add,
                                                       validators_to_retire):
            node_stash_accounts.append(validator_stash_account)
            nodes_to_register.append(node)

    log.info(f'funding the following stash accounts: {node_stash_accounts}')
    fund_accounts(substrate_client, node_stash_accounts, sudo_seed)
    if consensus == "poa":
        validator_session_keys_tasks = []
        log.info(f'setting up session keys for the following nodes: {nodes_to_register}')
        for node_to_register in nodes_to_register:
            validator_session_keys_tasks.append(setup_validators_session_keys(node_to_register))
        accounts_to_register = await asyncio.gather(*validator_session_keys_tasks)
        # remove empty strings from list (ie. don't register nodes which failed to generate session keys)
        accounts_to_register = list(filter(None, accounts_to_register))

        log.info(f'adding {len(accounts_to_register)} addresses to the validator set: {accounts_to_register}')
        register_validator_addresses(accounts_to_register)
    else:
        for node in nodes_to_register:
            validator_stash_mnemonic = get_node_stash_account_mnemonic(validators_root_seed, node)

            log.info(f'Rotate node session keys for {node}')
            node_session_key = rotate_node_session_keys(node_http_endpoint(node))

            log.info(f'Registering PoS Validator: {node}')
            status = setup_pos_validator(ws_endpoint, validator_stash_mnemonic, node_session_key)
            if status:
                log.info(f'Successfully set up PoS Validator: {node}')
            else:
                log.error(f'Fail to set up PoS Validator: {node}')


async def register_statefulset_validators(stateful_set_name):
    log.info(f'registering validators from stateful set: {stateful_set_name}')
    validator_pods = list_validator_pods(stateful_set_name)
    await register_validator_pods(validator_pods)


async def register_validator_nodes(nodes):
    log.info(f'registering the following validators nodes: {nodes} on {relay_chain_network_name}')
    pods_to_register = list(map(lambda pod_name: get_pod(pod_name), nodes))
    await register_validator_pods(pods_to_register)


async def deregister_validator_addresses(validator_addresses_to_deregister):
    ws_endpoint = get_relay_chain_rpc_url()
    sudo_seed = network_sudo_seed()
    log.info(
        f'removing {len(validator_addresses_to_deregister)} addresses from the validator set: {validator_addresses_to_deregister}')
    deregister_validators(ws_endpoint, sudo_seed, validator_addresses_to_deregister)


async def deregister_validator_pods(pods):
    log.info(f'deregistering validators pods on {relay_chain_network_name}')
    ws_endpoint = get_relay_chain_rpc_url()
    validator_set = get_validator_set(ws_endpoint)
    validators_to_add = get_validators_pending_addition(ws_endpoint)
    validators_to_retire = get_validators_pending_deletion(ws_endpoint)
    consensus = relay_chain_consensus()

    accounts_to_deregister = []
    pods_to_deregister = []
    for pod in pods:
        node = pod.metadata.name
        validator_account = get_validator_account_from_pod(pod)
        validator_account_registration_status = is_validator_address_already_registered(validator_account, validator_set, validators_to_add,
                                                validators_to_retire)
        log.debug(f'validator_stash_account={validator_account}')
        log.debug(f'validator_set={validator_set}')
        log.debug(f'validators_to_add={validators_to_add}')
        log.debug(f'validators_to_retire={validators_to_retire}')
        if validator_account_registration_status:
            log.debug(f'adding {node} (validatorAccount={validator_account}) to the nodes to deregister')
            accounts_to_deregister.append(validator_account)
            pods_to_deregister.append(pod.metadata.name)
        else:
            log.debug(f'skipping {node} (validatorAccount={validator_account}) deregistration as it is not currently registered')
    if accounts_to_deregister and consensus == "poa":
        log.info(f'The following accounts will be deregister: {accounts_to_deregister}')
        await deregister_validator_addresses(accounts_to_deregister)
    if pods_to_deregister and consensus == "pos":
        log.info(f'The following validators will be deregister: {pods_to_deregister}')
        for pod_name in pods_to_deregister:
            validator_stash_mnemonic = get_node_stash_account_mnemonic(derivation_root_seed(), pod_name)
            staking_chill(ws_endpoint, validator_stash_mnemonic)


async def deregister_validator_nodes(nodes):
    log.info(f'deregister the following validators on {relay_chain_network_name}: {nodes}')
    pods_to_deregister = list(map(lambda pod_name: get_pod(pod_name), nodes))
    await deregister_validator_pods(pods_to_deregister)


async def deregister_statefulset_validators(stateful_set_name):
    log.info(f'deregistering validators from stateful set: {stateful_set_name}')
    validator_pods = list_validator_pods(stateful_set_name)
    await deregister_validator_pods(validator_pods)


async def rotate_nodes_session_keys(stateful_set_name):
    log.info('starting to rotate validators session keys in statefulset: {}'.format(stateful_set_name))
    substrate_client = get_relay_chain_client()
    sudo_seed = network_sudo_seed()

    validator_pods = list_validator_pods(stateful_set_name)
    nodes_to_rotate_session_keys = []
    node_stash_accounts = []

    for pod in validator_pods:
        node_name = pod.metadata.name
        # rotate keys of nodes which don't have their validator account set in labels
        if 'validatorAccount' not in pod.metadata.labels:
            nodes_to_rotate_session_keys.append(node_name)

    log.info('making sure the following stash account are properly funded: {}'.format(node_stash_accounts))
    fund_accounts(substrate_client, node_stash_accounts, sudo_seed)
    validator_session_keys_tasks = []
    log.info('setting up session keys for the following nodes: {}'.format(nodes_to_rotate_session_keys))
    for node in nodes_to_rotate_session_keys:
        validator_session_keys_tasks.append(setup_validators_session_keys(node))

    session_keys_to_rotate = await asyncio.gather(*validator_session_keys_tasks)
    # remove empty strings from list
    session_keys_to_rotate = list(filter(None, session_keys_to_rotate))
    log.info(
        '{} session keys have been rotated and set: {}'.format(len(session_keys_to_rotate), session_keys_to_rotate))


def get_session_queued_keys():
    return get_queued_keys(get_relay_chain_client())


# Parachains
def list_parachains():
    substrate_client = get_relay_chain_client()

    # retrieve the list of parachains for which we have collators in the cluster
    collator_pods = list_collator_pods()
    # If the paraId is not set on pod labels, we fall back to 0
    cluster_parachain_tuple_set = set(
        map(lambda pod: (pod.metadata.labels.get('paraId', '0'), pod.metadata.labels.get('chain')), collator_pods))

    parachains = {}
    for cluster_parachain_tuple in cluster_parachain_tuple_set:
        para_id, chain = cluster_parachain_tuple
        parachains[para_id] = {'name': chain, 'location': 'in_cluster'}

    # retrieve parachain and parathread IDs
    parathread_ids = get_parathreads_ids(substrate_client)
    parachain_ids = get_parachains_ids(substrate_client)
    para_ids = parathread_ids + parachain_ids
    # retrieve on-chain para infos
    parachain_lifecycles = get_all_parachain_lifecycles(substrate_client)
    parachain_leases_count = get_all_parachain_leases_count(substrate_client)
    parachain_current_code_hashes = get_all_parachain_current_code_hashes(substrate_client)
    parachain_heads = get_all_parachain_heads(substrate_client)

    for para_id in para_ids:
        parachains[para_id] = {
            'name': relay_chain_network_name + '-para-' + str(para_id) if not parachains.get(para_id) else parachains[para_id][
                'name'],
            'lifecycle': parachain_lifecycles.get(para_id),
            'leases_count': parachain_leases_count.get(para_id),
            'current_code_hash': parachain_current_code_hashes.get(para_id),
            'head': parachain_heads.get(para_id),
            'location': 'external ' if not parachains.get(para_id) else parachains[para_id]['location'],
        }
    return parachains


async def onboard_parachain_by_id(para_id: str, force_queue_action: bool):
    log.info(f'starting to onboard parachain #{para_id}')
    relay_chain_client = get_relay_chain_client()
    sudo_seed = network_sudo_seed()
    parachain_pods = list_collator_pods(para_id)
    if parachain_pods:
        para_node_client = get_node_client(parachain_pods[0].metadata.name)
        node_para_id = get_parachain_id(parachain_pods[0])
        if node_para_id == para_id:
            state = get_parachain_head(para_node_client)
            wasm = get_chain_wasm(para_node_client)
            if state and wasm:
                permanent_slot_lease_period_length = get_permanent_slot_lease_period_length(relay_chain_client)
                log.info('Scheduling parachain #{}, state:{}, wasm: {}...{}, lease: {}'.format(
                    para_id, state, wasm[0:64], wasm[-64:], permanent_slot_lease_period_length))
                initialize_parachain(relay_chain_client, sudo_seed, para_id, state, wasm, permanent_slot_lease_period_length, force_queue_action)
            else:
                log.error(
                    'Error: Not enough parameters to Scheduling parachain para_id: {}, state:{}, wasm: {}...{}'.format(
                        para_id, state, wasm[0:64], wasm[-64:-1]))
        else:
            log.error('Node para_id: {} doesn\'t match the requested offboard para_id {}'.format(node_para_id, para_id))
    else:
        log.error(f"Couldn't find parachain pod for para_id={para_id}")


async def offboard_parachain_by_id(para_id: str, force_queue_action: bool):
    log.info(f'starting to offboard parachain #{para_id}')
    substrate_client = get_relay_chain_client()
    sudo_seed = network_sudo_seed()
    parachain_pods = list_collator_pods(para_id)
    para_id = get_parachain_id(parachain_pods[0])

    log.info('Scheduling cleanup of parachain: {}'.format(para_id))
    cleanup_parachain(substrate_client, sudo_seed, para_id, force_queue_action)


# Collators
def list_parachain_collators(para_id: str, stateful_set_name: str = ''):
    collator_pods = list_collator_pods(para_id, stateful_set_name)
    # Read the first collator pod chain metadata for this para_id to retrieve the chain name
    if collator_pods:
        chain_name = collator_pods[0].metadata.labels['chain']
    else:
        return []

    parachain_node_client = get_parachain_node_client(para_id)

    parachain_staking_selected_candidates = []
    parachain_staking_candidate_pool = []
    collator_selection_invulnerables = []
    collator_selection_candidates = []
    collator_selection_desired_candidates = None
    runtime = get_last_runtime_upgrade(parachain_node_client)
    try:
        # Get parachain staking pallet state for "moon*" chains
        if chain_name.startswith("moon"):
            parachain_staking_selected_candidates = parachain_node_client.query('ParachainStaking',
                                                                                'SelectedCandidates', params=[]).value
            parachain_staking_candidate_pool = parachain_node_client.query('ParachainStaking', 'CandidatePool',
                                                                            params=[]).value

        # Get collatorSelection pallet state if the pallet is present
        collator_selection_invulnerables = parachain_node_client.query('CollatorSelection', 'Invulnerables',
                                                                        params=[]).value
        collator_selection_candidates = parachain_node_client.query('CollatorSelection', 'Candidates', params=[]).value
        collator_selection_desired_candidates = parachain_node_client.query('CollatorSelection', 'DesiredCandidates',
                                                                            params=[]).value
    except Exception as err:
        log.info(f'Unable to get collator set: {err}')

    collators = []
    for pod in collator_pods:
        node_name = pod.metadata.name
        collator_account = get_collator_account_from_pod(pod)
        chain = pod.metadata.labels['chain']
        if chain.startswith("moon"):
            collator_status = get_moon_collator_status(collator_account, parachain_staking_selected_candidates,
                                                       parachain_staking_candidate_pool)
        else:
             collator_status = get_collator_status(collator_account, collator_selection_invulnerables,
                                                   collator_selection_candidates)
        pod_status = pod.status.phase
        http_endpoint = node_http_endpoint(node_name)
        collators.append({
            # same value for all nodes
            'location': 'in_cluster',
            'chain': chain,
            'desired_candidates': collator_selection_desired_candidates,
            'runtime': runtime,
            # uniq values
            'name': node_name,
            'account': collator_account,
            'status': collator_status,
            'pod_status': pod_status,
            'image': pod.spec.containers[0].image,
        })
    # add missing collators
    if not stateful_set_name:
        all_collators = []
        for c in collator_selection_invulnerables:
            all_collators.append({'id': c, 'type': "Invulnerable"})
        for c in collator_selection_candidates:
            all_collators.append({'id': c['who'], 'type': "Candidate"})
        for c in parachain_staking_selected_candidates:
            all_collators.append({'id': c, 'type': "SelectedCandidates"})
        for c in parachain_staking_candidate_pool:
            all_collators.append({'id': c['owner'], 'type': "CandidatePool"})
        i = 0
        for collator in all_collators:
            if not any(d['account'].lower() == collator['id'].lower() for d in collators):
                collators.append({
                    # same value for all nodes
                    'location': 'external',
                    'chain': chain,
                    'desired_candidates': collator_selection_desired_candidates,
                    # uniq values
                    'name': "unknown-" + chain + "-" + str(i),
                    'account': collator['id'],
                    'status': collator['type'],
                    'pod_status': '?',
                    'image': '?',
                    'uptime': '?',
                })
                i += 1
    return collators


async def register_collator_nodes(chain, nodes, ss58_format):
    collators_register_tasks = []
    for node_name in nodes:
        collators_register_tasks.append(collator_register(chain, node_name, ss58_format))
    accounts_to_register = await asyncio.gather(*collators_register_tasks)
    log.info('adding {} addresses to the collators set: {}'.format(len(accounts_to_register), accounts_to_register))
    return accounts_to_register


async def deregister_collator_nodes(chain, nodes, ss58_format):
    collators_deregister_tasks = []
    for node_name in nodes:
        collators_deregister_tasks.append(collator_deregister(chain, node_name, ss58_format))
    accounts_to_deregister = await asyncio.gather(*collators_deregister_tasks)
    log.info(
        'removing {} addresses from the collators set: {}'.format(len(accounts_to_deregister), accounts_to_deregister))
    return accounts_to_deregister


async def register_statefulset_collators(para_id: str, stateful_set_name: str):
    log.info('starting to register collators in statefulset {}'.format(stateful_set_name))
    collators_pods = list_collator_pods(para_id, stateful_set_name)
    chain = collators_pods[0].metadata.labels['chain']
    ss58_format = collators_pods[0].metadata.labels.get('ss58Format', '42')
    collator_node_names = list(map(lambda pod: pod.metadata.name, collators_pods))
    await register_collator_nodes(chain, collator_node_names, ss58_format)


async def deregister_statefulset_collators(para_id: str, stateful_set_name: str):
    log.info('starting to deregister collators in statefulset {}'.format(stateful_set_name))
    collators_pods = list_collator_pods(para_id, stateful_set_name)
    chain = collators_pods[0].metadata.labels['chain']
    ss58_format = collators_pods[0].metadata.labels.get('ss58Format', '42')
    collator_node_names = list(map(lambda pod: pod.metadata.name, collators_pods))
    await deregister_collator_nodes(chain, collator_node_names, ss58_format)


async def add_invulnerable_collators(para_id, nodes=[], addresses=[]):
    log.info(f'Adding invulnerables collators to parachain #{para_id}; nodes={nodes} and addresses={addresses}')
    current_invulnerables = get_collator_selection_invulnerables(para_id)
    invulnerables_to_add = []
    for node_name in nodes:
        node_collator_account = get_substrate_node(node_name).get("collator_account")
        if node_collator_account:
            invulnerables_to_add.append(node_collator_account)
    for account_address in addresses:
        invulnerables_to_add.append(account_address)
    invulnerables = list(set(current_invulnerables).union(set(invulnerables_to_add)))
    await set_collator_selection_invulnerables(para_id, invulnerables)


async def remove_invulnerable_collators(para_id, nodes=[], addresses=[]):
    log.info(f'Removing invulnerables collators to parachain #{para_id}; nodes={nodes} and addresses={addresses}')
    current_invulnerables = get_collator_selection_invulnerables(para_id)
    invulnerables_to_remove = []
    for node_name in nodes:
        node_collator_account = get_substrate_node(node_name).get("collator_account")
        if node_collator_account:
            invulnerables_to_remove.append(node_collator_account)
    for account_address in addresses:
        invulnerables_to_remove.append(account_address)
    invulnerables = list(set(current_invulnerables).difference(set(invulnerables_to_remove)))
    await set_collator_selection_invulnerables(para_id, invulnerables)


async def set_collator_nodes_keys_on_chain(para_id, nodes=[], statefulset=''):
    if statefulset:
        statefulset_nodes = map(lambda node: node.node_name, list_substrate_nodes(statefulset))
        nodes.extend(statefulset_nodes)
    for node_name in nodes:
        ss58_format = get_substrate_node(node_name).get("ss58_format")
        collator_set_keys(node_name, para_id, ss58_format)


