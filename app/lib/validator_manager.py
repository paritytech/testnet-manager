import logging
from substrateinterface import Keypair
from app.lib.substrate import substrate_query_url, substrate_sudo_call, get_substrate_client, substrate_call,\
    substrate_batchall_call
from app.config.network_configuration import network_consensus
from app.lib.session_keys import decode_session_key

log = logging.getLogger('validator_manager')


def get_validator_set(ws_endpoint):
    return substrate_query_url(ws_endpoint, "Session", "Validators")


def register_validators(ws_endpoint, sudo_seed, stash_account_addresses):
    substrate_client = get_substrate_client(ws_endpoint)
    keypair = Keypair.create_from_seed(sudo_seed)
    payload = substrate_client.compose_call(
        call_module='ValidatorManager',
        call_function='register_validators',
        call_params={
            'validators': stash_account_addresses
        }
    )
    substrate_sudo_call(substrate_client, keypair, payload)


def deregister_validators(ws_endpoint, sudo_seed, stash_account_addresses):
    substrate_client = get_substrate_client(ws_endpoint)
    keypair = Keypair.create_from_seed(sudo_seed)
    payload = substrate_client.compose_call(
        call_module='ValidatorManager',
        call_function='deregister_validators',
        call_params={
            'validators': stash_account_addresses
        }
    )
    substrate_sudo_call(substrate_client, keypair, payload)


def get_validators_pending_addition(ws_endpoint):
    if network_consensus() == "poa":
        return substrate_query_url(ws_endpoint, "ValidatorManager", "ValidatorsToAdd")
    else:
        active_validators = substrate_query_url(ws_endpoint, "Session", "Validators")
        staking_validators = staking_validators_set(ws_endpoint)
        return list(set(staking_validators) - set(active_validators))


def get_validators_pending_deletion(ws_endpoint):
    if network_consensus() == "poa":
        return substrate_query_url(ws_endpoint, "ValidatorManager", "ValidatorsToRetire")
    else:
        active_validators = substrate_query_url(ws_endpoint, "Session", "Validators")
        staking_validators = staking_validators_set(ws_endpoint)
        return list(set(active_validators) - set(staking_validators))


def setup_pos_validator(ws_endpoint, session_key,  stash_seed, controller_seed=None):
    batch_call = []
    substrate_client = get_substrate_client(ws_endpoint)
    stash_keypair = Keypair.create_from_uri(stash_seed)

    batch_call.append(substrate_client.compose_call(
            call_module='Staking',
            call_function='bond',
            call_params={
                'controller': stash_keypair.ss58_address,
                'value': 1 * 10 ** 11,
                'payee': "Staked"
            }
        )
    )

    if type(session_key) == str:
        session_key = decode_session_key(substrate_client,session_key)
    batch_call.append(substrate_client.compose_call(
            call_module='Session',
            call_function='set_keys',
            call_params={
                'keys': session_key,
                'proof': ''
            }
        )
    )

    batch_call.append(substrate_client.compose_call(
            call_module='Staking',
            call_function='validate',
            call_params={
                'prefs': {
                    'commission': 100000000,  # 10%
                    'blocked': False
                }
            }
        )
    )

    if controller_seed:
        controller_keypair = Keypair.create_from_uri(controller_seed)
        batch_call.append(substrate_client.compose_call(
                call_module='Staking',
                call_function='set_controller',
                call_params={
                    'controller': controller_keypair.ss58_address,
                }
            )
        )

    result = substrate_batchall_call(substrate_client, stash_keypair, batch_call, wait=True)
    if result and result.is_success:
        return True
    else:
        return False


def staking_chill(ws_endpoint, stash_seed):
    substrate_client = get_substrate_client(ws_endpoint)
    keypair = Keypair.create_from_uri(stash_seed)
    payload = substrate_client.compose_call(
        call_module='Staking',
        call_function='chill'
    )
    substrate_call(substrate_client, keypair, payload)


def staking_validators_set(ws_endpoint):
    substrate_client = get_substrate_client(ws_endpoint)
    all_validators = substrate_client.query_map('Staking', 'Validators')
    result = []
    for validator in all_validators:
        result.append(validator[0].value)
    return result
