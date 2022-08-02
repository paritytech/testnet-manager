import logging
import traceback

from substrateinterface import Keypair
from app.lib.substrate import substrate_call
from app.lib.balance_utils import transfer_funds
from app.lib.substrate import get_node_client, substrate_sudo_relay_xcm_call
from app.config.network_configuration import network_validators_root_seed
from app.lib.session_keys import set_node_session_key
from app.lib.node_utils import inject_key

log = logging.getLogger('collator_mint')


def register_mint_collator(node_name, ss58_format=0, rotate_key=False):
    try:
        # 1. Generating stash account keypair
        node_client = get_node_client(node_name)
        collator_root_seed = network_validators_root_seed()
        collator_aura_key = collator_root_seed + "//collator//" + node_name
        keypair_rich = Keypair.create_from_uri(collator_root_seed, ss58_format=ss58_format)
        keypair = Keypair.create_from_uri(collator_aura_key, ss58_format=ss58_format)
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
                result = transfer_funds(node_client, keypair_rich, keypair.ss58_address, candidacy_bond + 1 * 10 ** 9)
                if result == None:
                    # exit, failed to fund account
                    log.error("Unable fund account: {}, node: {}".format(
                        keypair.ss58_address, getattr(node_client, 'url', 'NO_URL')))
                    return None


            # # 2. inject key
            inject_key(node_client, collator_aura_key)

            # 3. Generating and setting session keys
            session_key = node_client.rpc_request(method="author_rotateKeys", params=[])['result']
            result = set_node_session_key(node_client.url, collator_aura_key, session_key)
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


def deregister_mint_collator(node_name, ss58_format=0):
    node_client = get_node_client(node_name)
    collator_root_seed = network_validators_root_seed()
    collator_aura_key = collator_root_seed + "//collator//" + node_name
    keypair = Keypair.create_from_uri(collator_aura_key, ss58_format=ss58_format)
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
