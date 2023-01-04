import logging
import time
import traceback

from substrateinterface import Keypair

from app.config.network_configuration import network_root_seed, get_network_ss58_format, \
    network_sudo_seed
from app.lib.balance_utils import transfer_funds, teleport_funds
from app.lib.collator_account import get_derived_collator_keypair, get_derived_collator_seed
from app.lib.node_utils import inject_key, node_keystore_has_key, check_has_session_keys
from app.lib.session_keys import set_node_session_key
from app.lib.stash_accounts import get_account_funds
from app.lib.substrate import get_node_client, substrate_sudo_relay_xcm_call, get_relay_chain_client
from app.lib.substrate import substrate_call

log = logging.getLogger('collator_mint')


def register_mint_collator(node_name, ss58_format, rotate_key=False):
    try:
        # 1. Generating stash account keypair
        node_client = get_node_client(node_name)
        keypair_rich = Keypair.create_from_uri(network_root_seed(), ss58_format=int(ss58_format))
        collator_seed = get_derived_collator_seed(node_client)
        keypair = get_derived_collator_keypair(node_name, ss58_format)
        candidates = node_client.query('CollatorSelection', 'Candidates').value

        if not any(d['who'].lower() == keypair.ss58_address.lower() for d in candidates) or rotate_key:
            # 2. Check enough funds
            candidacy_bond = node_client.query('CollatorSelection', 'CandidacyBond', params=[]).value
            account_info = node_client.query('System', 'Account', params=[keypair.ss58_address]).value
            log.info("Check that {}({}) have more than {}".format(
                keypair.ss58_address, account_info['data']['free'], candidacy_bond))
            if account_info['data']['free'] < candidacy_bond + 0.1 * 10 ** 9:
                print("Funding {}".format(keypair.ss58_address))
                # candidacyBond + 1 tx fee
                result = transfer_funds(node_client, keypair_rich, [keypair.ss58_address], candidacy_bond + 1 * 10 ** 9)
                if result == None:
                    # exit, failed to fund account
                    log.error("Unable fund account: {}, node: {}".format(
                        keypair.ss58_address, getattr(node_client, 'url', 'NO_URL')))
                    return None


            # # 2. inject key
            inject_key(node_client, collator_seed)

            # 3. Generating and setting session keys
            session_key = node_client.rpc_request(method="author_rotateKeys", params=[])['result']
            result = set_node_session_key(node_client.url, collator_seed, session_key)
            if not result:
                # exit, failed to rotate key
                log.error("Unable to rotate session key for node: {}".format(getattr(node_client, 'url', 'NO_URL')))
                return None

            # 4. Increase the desired candidate count
            desired_candidates = node_client.query('CollatorSelection', 'DesiredCandidates')
            new_desired_candidates = len(node_client.query('CollatorSelection', 'Candidates').value) + 1
            log.info("Increase the desired candidate count from {} to {}".format(desired_candidates, new_desired_candidates))
            call = node_client.compose_call(
                call_module='CollatorSelection',
                call_function='set_desired_candidates',
                call_params={
                    'max': new_desired_candidates
                }
            )

            encoded_call = call.encode()
            para_id = node_client.query('ParachainInfo', 'ParachainId', params=[]).value
            receipt = substrate_sudo_relay_xcm_call(para_id, encoded_call)
            if receipt and receipt.is_success:
                log.info("✅ Success: desired candidate increased to {}".format(new_desired_candidates))
            else:
                log.error("Failed to run xcm call, network: {}, para_id {}, message: {}, err: ".format(
                    para_id, encoded_call, getattr(receipt, 'error_message', None)))
                return None

            # 5. Register as Collator candidate
            call = node_client.compose_call(
                call_module='CollatorSelection',
                call_function='register_as_candidate',
            )
            receipt = substrate_call(node_client, keypair, call)
            if receipt and receipt.is_success:
                return keypair.ss58_address
            else:
                log.error("Unable to register as candidate node: {}, Error: {}".format(
                    getattr(node_client, 'url', 'NO_URL'), getattr(receipt, 'error_message', None)))
                return None
        else:
            log.info("Collator is already in candidate list ({}, {})".format(keypair.ss58_address, getattr(node_client, 'url', 'NO_URL')))
            return keypair.ss58_address

    except Exception as e:
        log.error("Unable to register_mint_collator. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None


def collator_set_keys(node_name, para_id, ss58_format):
    try:
        # 1. Get collator account keypair
        collator_keypair = get_derived_collator_keypair(node_name, ss58_format)
        collator_account_address = collator_keypair.ss58_address
        # 2. Check funds
        log.info("Check that {} has enough funds".format(collator_account_address))
        node_client = get_node_client(node_name)
        collator_account_funds = get_account_funds(node_client.url, collator_account_address)
        # 3. If insufficient, add funds with teleport
        if collator_account_funds < 0.5 * 10 ** 12:
            relay_chain_client = get_relay_chain_client()
            sudo_keypair = Keypair.create_from_seed(network_sudo_seed())
            log.info(f"Funding {collator_account_address}[ss58format={ss58_format}](funds={collator_account_funds}) via Teleport from relay-chain")
            # Get corresponding collator account address on the relay-chain (with the relay-chain ss58 format)
            relay_chain_collator_account = get_derived_collator_keypair(node_name, get_network_ss58_format()).ss58_address
            teleport_result = teleport_funds(relay_chain_client, sudo_keypair, para_id, [relay_chain_collator_account], 1 * 10 ** 12)
            if not teleport_result:
                log.error("Unable fund account: {}, node: {}".format(
                    collator_account_address, getattr(relay_chain_client, 'url', 'NO_URL')))
                return None
            log.info("Waiting 1 minute for teleport to complete")
            time.sleep(60)
        # 4. Check node has aura key
        aura_public_key = "0x" + collator_keypair.public_key.hex()
        if not node_keystore_has_key(node_client, 'aura', aura_public_key):
            log.error(f'Node ({node_name}) doesn\'t have the required aura key in its keystore')
            return None
        # 5. Setting aura key on chain via "set session key" if not already set
        if check_has_session_keys(node_client, {'aura': aura_public_key}):
            set_session_key_result = set_node_session_key(node_client.url, collator_keypair.seed_hex, aura_public_key)
            if not set_session_key_result:
                log.error(f"Unable to set session key for node: {node_client.url}, session_key={aura_public_key}")
                return None
    except Exception as e:
        log.error("Unable to collator_set_keys. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None


def deregister_mint_collator(node_name, ss58_format):
    node_client = get_node_client(node_name)
    collator_seed = get_derived_collator_seed(node_name)
    keypair = Keypair.create_from_uri(collator_seed, ss58_format=int(ss58_format))
    try:
        candidates = node_client.query('CollatorSelection', 'Candidates').value
        if any(d['who'].lower() == keypair.ss58_address.lower() for d in candidates):
            # 1. Decrease the desired candidate count
            desired_candidates = node_client.query('CollatorSelection', 'DesiredCandidates')
            new_desired_candidates = len(node_client.query('CollatorSelection', 'Candidates').value) - 1
            log.info(
                "Decrease the desired candidate count from {} to {}".format(desired_candidates, new_desired_candidates))
            call = node_client.compose_call(
                call_module='CollatorSelection',
                call_function='set_desired_candidates',
                call_params={
                    'max': new_desired_candidates
                }
            )
            encoded_call = call.encode()
            para_id = node_client.query('ParachainInfo', 'ParachainId', params=[]).value
            receipt = substrate_sudo_relay_xcm_call(para_id, encoded_call)
            if receipt and receipt.is_success:
                log.info("✅ Success: desired candidate Decreased to {}".format(new_desired_candidates))
            else:
                log.error("Failed to run xcm call, network: {}, para_id {}, message: {}, err: ".format(
                    para_id, encoded_call, getattr(receipt, 'error_message', None)))
                return None
            # leave candidate pool
            call = node_client.compose_call(
                call_module='CollatorSelection',
                call_function='leave_intent'
            )
            receipt = substrate_call(node_client, keypair, call)
            if receipt and receipt.is_success:
                log.info("✅ Success: leave_intent {}".format(keypair.ss58_address))
                return True
            else:
                # 'Deregister `origin` as a collator candidate. Note that the collator can only leave on
                # session change. The `CandidacyBond` will be unreserved immediately.
                # This call will fail if the total number of candidates would drop below `MinCandidates`.
                # This call is not available to `Invulnerable` collators.'
                log.error("Unable to deregister a candidate node: {}, Error: {}".format(
                    getattr(node_client, 'url', 'NO_URL'), getattr(receipt, 'error_message', None)))
                return False
        else:
            log.info("Collator is already deregistered ({}, {})".format(keypair.ss58_address,
                                                                        getattr(node_client, 'url', 'NO_URL')))
            return True
    except Exception as e:
        log.error("Unable to deregister_mint_collator. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None
