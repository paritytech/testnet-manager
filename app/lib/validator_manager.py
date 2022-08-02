import logging
from substrateinterface import Keypair
from app.lib.substrate import substrate_query_url, substrate_sudo_call, get_substrate_client

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


def get_validators_to_add(ws_endpoint):
    return substrate_query_url(ws_endpoint, "ValidatorManager", "ValidatorsToAdd")


def get_validators_to_retire(ws_endpoint):
    return substrate_query_url(ws_endpoint, "ValidatorManager", "ValidatorsToRetire")
