import logging

from substrateinterface import Keypair, KeypairType
from app.lib.substrate import substrate_batchall_call, substrate_call, substrate_rpc_request, get_chain_properties

log = logging.getLogger('balance_utils')


def get_funds(substrate_client, address):
    try:
        result = substrate_client.query(
            module='System',
            storage_function='Account',
            params=[address]
        )
        if result.value:
            return int(result.value['data']['free'])
        else:
            return 0
    except Exception:
        return 0


def transfer_funds(substrate_client, from_account_keypair, target_account_address_list, transfer_amount, add_token_decimals=True):
    chain_properties = get_chain_properties(substrate_client)
    log.info(
        f"Transferring funds: {transfer_amount} {chain_properties.get('tokenSymbol','UNIT')} from {from_account_keypair} to Account={target_account_address_list}")
    if add_token_decimals:
        token_decimals = chain_properties.get('tokenDecimals', 12)
    else:
        token_decimals = 1
    batch_call = []
    for target_account_address in target_account_address_list:
        batch_call.append(substrate_client.compose_call(
        call_module='Balances',
        call_function='transfer_keep_alive',
        call_params={
            'dest': target_account_address,
            'value': transfer_amount * 10 ** token_decimals
        }))
    receipt = substrate_batchall_call(substrate_client, from_account_keypair, batch_call)
    if receipt and receipt.is_success:
        return True
    else:
        log.error("Balance Transfer to Accounts={} failed. Error: {}".format(
            target_account_address_list, getattr(receipt, 'error_message', None)))
        return None


def teleport_funds(substrate_client, from_account_keypair, para_id, target_account_address_list, transfer_amount):
    chain_properties = get_chain_properties(substrate_client)
    log.info(
        f"Teleporting funds: {transfer_amount} {chain_properties.get('tokenSymbol','UNIT')} from {from_account_keypair} to Para #{para_id} Account={target_account_address_list}")
    token_decimals = chain_properties.get('tokenDecimals', 12)
    batch_call = []
    for address in target_account_address_list:
        target_account_public_key = Keypair(ss58_address=address, crypto_type=KeypairType.SR25519).public_key
        batch_call.append(substrate_client.compose_call(
        call_module='XcmPallet',
        call_function='limited_teleport_assets',
        call_params={
            'dest': {
                'V3': {
                    "parents": 0,
                    'interior': {
                        'X1': {
                            'Parachain': para_id
                        }
                    }
                }
            },
            'beneficiary': {
                'V3': {
                    'parents': 0,
                    'interior': {
                        'X1': {
                            'AccountId32': {
                                'network': None,
                                'id': target_account_public_key
                            }
                        }
                    }
                }
            },
            'assets': {
                'V3': [[
                    {
                        'id': {
                            'Concrete': {
                                'parents': 0,
                                'interior': 'Here'
                            }
                        },
                        'fun': {
                            'Fungible': transfer_amount * 10 ** token_decimals
                        }
                    }
                ]]
            },
            'fee_asset_item': 0,
            'weight_limit': 'Unlimited',
            }
        ))
    receipt = substrate_batchall_call(substrate_client, from_account_keypair, batch_call)
    if receipt and receipt.is_success:
        return True
    else:
        log.error("Teleport to Accounts={} failed. Error: {}".format(
            target_account_address_list, getattr(receipt, 'error_message', None)))
        return None


def fund_accounts(substrate_client, addresses, funding_account_seed):
    funding_account_keypair = Keypair.create_from_seed(funding_account_seed)
    target_account_address_list = []
    token_decimals = get_chain_properties(substrate_client).get('tokenDecimals', 12)
    for address in addresses:
        address_funds = get_funds(substrate_client, address)
        log.info('address={} (funds={})'.format(address, address_funds))
        if address_funds < 0.5 * 10 ** token_decimals:  # < 0.5 UNIT
            log.info(
                'address={} is not properly funded (funds={}), schedule transferring funds from sudo account'.format(
                    address, address_funds))
            target_account_address_list.append(address)
    transfer_funds(substrate_client, funding_account_keypair, target_account_address_list, 1)
