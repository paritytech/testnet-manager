import logging

from substrateinterface import Keypair

from app.lib.substrate import substrate_query_url

log = logging.getLogger('stash_accounts')


def get_node_stash_account_mnemonic(root_seed, node_name):
    return f'{root_seed}//{node_name}//stash'


def get_node_stash_keypair(root_seed, node_name):
    node_stash_account_mnemonic = get_node_stash_account_mnemonic(root_seed, node_name)
    return Keypair.create_from_uri(node_stash_account_mnemonic)


def get_derived_node_stash_account_address(root_seed, node_name):
    node_stash_keypair = get_node_stash_keypair(root_seed, node_name)
    return node_stash_keypair.ss58_address


def get_account_funds(ws_endpoint, account_address):
    funds_data = substrate_query_url(ws_endpoint, 'System', 'Account', [account_address])['data']
    # if account is not created the data is empty.
    if 'free' in funds_data:
        return funds_data['free']
    else:
        return None
