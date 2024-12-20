import logging
from math import floor

from substrateinterface.exceptions import StorageFunctionNotFound

from app.lib.substrate import substrate_batchall_call, get_node_client, \
    substrate_sudo_relay_xcm_call, substrate_call, get_query_weight
from substrateinterface import Keypair
from app.lib.kubernetes_client import list_collator_pods
from substrateinterface.utils.hasher import blake2_256
import time

log = logging.getLogger('collator_manager')


def get_parachain_node_client(para_id):
    parachain_pods = list_collator_pods(para_id)
    return get_node_client(parachain_pods[0].metadata.name)


# returns current parachains list
def get_parachains_ids(substrate_client):
    parachains = substrate_client.query('Paras', 'Parachains', params=[])
    parachain_ids = parachains.value
    return parachain_ids


# returns current parathread list (including UpgradingParathread, DowngradingParathread, etc.)
def get_parathreads_ids(substrate_client):
    paras_lifecycles = get_all_parachain_lifecycles(substrate_client)
    parathread_ids = list(para_id for (para_id, lifecycle) in paras_lifecycles.items() if lifecycle != 'Parachain')
    return parathread_ids


# return parachain lease count
def get_parachain_leases_count(substrate_client, para_id):
    leases = substrate_client.query('Slots', 'Leases', params=[para_id])
    parachain_leases_count = len(leases)
    return parachain_leases_count


# returns leases count of all paras
def get_all_parachain_leases_count(substrate_client):
    leases = substrate_client.query_map('Slots', 'Leases')
    result = {}
    for para_lifecycle in leases:
        para_id = para_lifecycle[0].value
        result[para_id] = len(para_lifecycle[1].value)
    return result


# returns Parachain Lifecycle
def get_parachain_lifecycles(substrate_client, para_id):
    lifecycles = substrate_client.query('Paras', 'ParaLifecycles', params=[para_id])
    return lifecycles.value


# returns lifecycles of all paras
def get_all_parachain_lifecycles(substrate_client):
    paras_lifecycles = substrate_client.query_map('Paras', 'ParaLifecycles')
    result = {}
    for para_lifecycle in paras_lifecycles:
        # If all parachins are off-boarded, ParaLifecycles will return list of None objets without 'value' attribute.
        if getattr(para_lifecycle[0], "value", None):
            para_id = para_lifecycle[0].value
            result[para_id] = para_lifecycle[1].value
    return result


# returns current code hashes of all paras
def get_all_parachain_current_code_hashes(substrate_client):
    paras_current_code_hashes = substrate_client.query_map('Paras', 'CurrentCodeHash')
    result = {}
    for para_code_hash in paras_current_code_hashes:
        para_id = para_code_hash[0].value
        result[para_id] = para_code_hash[1].value
    return result


# returns current code hashes of all paras
def get_all_parachain_heads(substrate_client):
    paras_heads = substrate_client.query_map('Paras', 'Heads')
    result = {}
    for paras_head in paras_heads:
        para_id = paras_head[0].value
        result[para_id] = paras_head[1].value
    return result


def get_parachain_id(pod):
    # node may not be available, or pallet is not exist
    try:
        if 'paraId' in pod.metadata.labels:
            para_id = pod.metadata.labels['paraId']
        else:
            node_client = get_node_client(pod.metadata.name)
            if node_client is not None:
                para_id = node_client.query('ParachainInfo', 'ParachainId', params=[]).value
            else:
                para_id = None
        return para_id
    except Exception as e:
        log.error('Unable to get parachain id: {}'.format(e))
        return None


def get_chain_wasm(node_client):
    # query for Substrate.Code see: https://github.com/polkascan/py-substrate-interface/issues/190
    block_hash = node_client.get_chain_head()
    parachain_wasm = node_client.get_storage_by_key(block_hash, "0x3a636f6465")
    return parachain_wasm


def convert_header(plain_header, substrate):
    raw_header = '0x'
    raw_header += plain_header['parentHash'].replace('0x', '')
    raw_header += str(substrate.encode_scale('Compact<u32>', int(plain_header['number'], 16))).replace('0x', '')
    raw_header += plain_header['stateRoot'].replace('0x', '')
    raw_header += plain_header['extrinsicsRoot'].replace('0x', '')
    raw_header += str(substrate.encode_scale('Compact<u32>', len(plain_header['digest']['logs']))).replace('0x', '')
    for lg in plain_header['digest']['logs']:
        raw_header += lg.replace('0x', '')
    return raw_header


def get_parachain_head(node_client):
    block_header = node_client.rpc_request(method="chain_getHeader", params=[])
    return convert_header(block_header['result'], node_client)


# get the lease period duration (in number of blocks)
def get_lease_period_duration(substrate_client):
    return substrate_client.get_constant("Slots", "LeasePeriod").value


def get_temporary_slot_lease_period_length(substrate_client):
    return substrate_client.get_constant("AssignedSlots", "TemporarySlotLeasePeriodLength").value


def get_permanent_slot_lease_period_length(substrate_client):
    return substrate_client.get_constant("AssignedSlots", "PermanentSlotLeasePeriodLength").value


def initialize_parachain(substrate_client, sudo_seed, para_id, state, wasm, lease_period_count=0, force_queue_action=True, is_parachain=True):
    batch_call = []
    keypair = Keypair.create_from_seed(sudo_seed)
    batch_call.append(substrate_client.compose_call(
        call_module='ParasSudoWrapper',
        call_function='sudo_schedule_para_initialize',
        call_params={
            'id': para_id,
            'genesis': {
                'genesis_head': state,
                'validation_code': wasm,
                'parachain': is_parachain, # legacy param
                'para_kind': is_parachain # new param introduced in https://github.com/paritytech/polkadot/pull/6198
            }
        }
    ))
    if lease_period_count != 0:
        lease_period_duration = get_lease_period_duration(substrate_client)
        block_height = substrate_client.get_block()['header']['number']
        current_lease_period_number = floor(block_height / lease_period_duration)
        batch_call.append(substrate_client.compose_call(
            call_module='Slots',
            call_function='force_lease',
            call_params={
                'para': para_id,
                'leaser': keypair.ss58_address,
                'amount': 0,
                'period_begin': current_lease_period_number,
                'period_count': lease_period_count
            }
        ))
    if force_queue_action:
        batch_call.append(substrate_client.compose_call(
            call_module='Paras',
            call_function='force_queue_action',
            call_params={
                'para': para_id
            }
        ))
    return substrate_batchall_call(substrate_client, keypair, batch_call, True, True)


def cleanup_parachain(substrate_client, sudo_seed, para_id, force_queue_action=True):
    keypair = Keypair.create_from_seed(sudo_seed)
    batch_call = []
    batch_call.append(substrate_client.compose_call(
        call_module='ParasSudoWrapper',
        call_function='sudo_schedule_para_cleanup',
        call_params={
            'id': para_id
        }
    ))
    if force_queue_action:
        batch_call.append(substrate_client.compose_call(
            call_module='Paras',
            call_function='force_queue_action',
            call_params={
                'para': para_id
            }
        ))
    return substrate_batchall_call(substrate_client, keypair, batch_call, True, True)


def parachain_runtime_upgrade(runtime_name, para_id, runtime_wasm, check_version=True):
    log.info(f'Upgrading para-chain #{para_id} runtime to {runtime_name}')
    # Doc: https://github.com/paritytech/cumulus/issues/764
    para_client = get_parachain_node_client(para_id)
    code = '0x' + runtime_wasm.hex()
    code_hash = f'0x{blake2_256(runtime_wasm).hex()}'

    log.info('Code hash: {}'.format(code_hash))
    # Construct System.authorizeUpgrade(hash) call on the parachain and grab the encoded call
    call_function_metadata = para_client.get_metadata_call_function("System", "authorize_upgrade")
    if len(call_function_metadata['fields']) == 2:
        call_params = {
            'code_hash': code_hash,
            'check_version': check_version
        }
    else:
        call_params = {'code_hash': code_hash}
    authorize_upgrade = para_client.compose_call(
        call_module='System',
        call_function='authorize_upgrade',
        call_params=call_params
    )
    weight = get_query_weight(para_client, authorize_upgrade)
    receipt = substrate_sudo_relay_xcm_call(para_id, authorize_upgrade.encode(), weight)
    if receipt and receipt.is_success:
        log.info('Successfully sent System.authorizeUpgrade(hash) on Relaychain')
        log.info('https://polkadot.js.org/apps/#/explorer/query/{}'.format(receipt.block_hash))
    else:
        err = "Unable to send System.authorizeUpgrade(hash) on Relaychain. Error: {}".format(
            getattr(receipt, 'error_message', None))
        log.error(err)
        return False, err

    # After XCM dispatch (as pointed out by Document Runtime Upgrade Process #764
    # we need to wait for both the Relay Chain block as well as the Parachain block that will process the XCM),
    # submit the compact.compressed.wasm file using the unsigned transaction parachainSystem.enactAuthorizedUpgrade.
    # Anyone can submit this extrinsic. Trouble Shooting: 1010: Invalid Transaction: Transaction call is not
    # expected. means the XCM was not yet processed on the parachain side so it does not recognize the blob. A
    # collator restart will reset the transaction banning as a workaround.
    log.info('Waiting 30s for parachain to receive AuthorizedUpgrade XCM')
    for i in range(30):
        time.sleep(2)
        authorized_upgrade = para_client.query('System', 'AuthorizedUpgrade')
        if authorized_upgrade.value:
            break
        if i == 29:
            err = "Timeout, parachain did not received AuthorizedUpgrade message"
            log.error(err)
            return False, err

    # After dispatch, submit the compact.compressed.wasm file using the unsigned transaction
    # system.applyAuthorizedUpgrade. Anyone can submit this extrinsic.
    apply_upgrade = para_client.compose_call(
        call_module='System',
        call_function='apply_authorized_upgrade',
        call_params={
            'code': code
        }
    )
    receipt = substrate_call(para_client, None, apply_upgrade)
    if receipt and receipt.is_success:
        msg = f'Successfully sent system.applyAuthorizedUpgrade on Parachain #{para_id} for {runtime_name} \n' \
              f'Check results here: https://polkadot.js.org/apps/#/explorer/query/{receipt.block_hash}'
        log.info(msg)
        return True, msg
    else:
        err = f'Unable to sent system.applyAuthorizedUpgrade on Parachain #{para_id} for {runtime_name} \n' \
              f'Error: {getattr(receipt, "error_message", None)}'
        log.error(err)
        return False, err
