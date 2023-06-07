import logging

from substrateinterface import Keypair

from app.config.network_configuration import network_root_seed
from app.lib.balance_utils import transfer_funds
from app.lib.kubernetes_client import get_pod
from app.lib.network_utils import get_validator_account_from_pod
from app.lib.substrate import get_chain_properties, substrate_batchall_call

log = logging.getLogger('staking_utils')


async def create_nominators_for_validator_node(substrate_client, funding_account_keypair, node_name, nominator_count, nominate_amount):
    log.info(f"Create {nominator_count} nominators for validator '{node_name}' with '{nominate_amount}' bounded funds for each")
    pod = get_pod(node_name)
    validator_account = get_validator_account_from_pod(pod)
    nominator_indexes = [*range(0, nominator_count)]
    nominator_seeds = list(map(lambda index: get_validator_nominator_mnemonic(node_name, index), nominator_indexes))
    nominator_accounts = list(map(lambda seed: Keypair.create_from_uri(seed).ss58_address, nominator_seeds))

    # Fund nominator accounts and execute bound + nominate
    transfer_funds(substrate_client, funding_account_keypair, nominator_accounts, nominate_amount + 1)
    for nominator_seed in nominator_seeds:
        nominator_keypair = Keypair.create_from_uri(nominator_seed)
        # If account is not already a nominator set up the nomination
        if not check_is_nominator(substrate_client, nominator_keypair):
            staking_create_nominator(substrate_client, nominator_keypair, [validator_account], nominate_amount)


def get_validator_nominator_mnemonic(validator_name, nominator_index):
    return f'{network_root_seed()}//{validator_name}//{nominator_index}'


def check_is_nominator(substrate_client, nominator_keypair):
    nominators_for_account = substrate_client.query('Staking', 'Nominators', params=[nominator_keypair.ss58_address])
    return nominators_for_account and nominators_for_account.value and nominators_for_account.value["targets"] and len(nominators_for_account.value["targets"]) >= 1


def staking_create_nominator(substrate_client, nominator_keypair, target_validator_addresses, bound_amount=1):
    nominator_address =  nominator_keypair.ss58_address
    log.info(f"Create nominators for {nominator_address}: target_validators={target_validator_addresses}, bound_amount={bound_amount}")

    chain_properties = get_chain_properties(substrate_client)
    token_decimals = chain_properties.get('tokenDecimals', 12)

    batch_call = [substrate_client.compose_call(
        call_module='Staking',
        call_function='bond',
        call_params={
            'controller': nominator_address,
            'value': bound_amount * 10 ** token_decimals,
            'payee': "Staked"
        }
    ), substrate_client.compose_call(
        call_module='Staking',
        call_function='nominate',
        call_params={
            'targets': target_validator_addresses
        }
    )]

    result = substrate_batchall_call(substrate_client, nominator_keypair, batch_call, wait=True)
    if result and result.is_success:
        if any(e.value['event_id'] == "BatchInterrupted" for e in result.triggered_events):
            log.error("Batch call failed: BatchInterrupted for stash {}, extrinsic_hash: {}, block_hash: {}".format(
                nominator_keypair.ss58_address, result.extrinsic_hash, result.block_hash))
            return False
        else:
            return True
