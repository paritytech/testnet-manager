import logging

from substrateinterface import Keypair
from app.lib.balance_utils import transfer_funds, teleport_funds
from app.lib.substrate import substrate_query_url, get_substrate_client


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
    return substrate_query_url(ws_endpoint, 'System', 'Account', [account_address])['data']['free']


def fund_account(ws_endpoint, funding_account_seed, target_account_address):
    substrate_client = get_substrate_client(ws_endpoint)
    keypair = Keypair.create_from_seed(funding_account_seed)
    transfer_funds(substrate_client, keypair, [target_account_address], 1 * 10 ** 12)
