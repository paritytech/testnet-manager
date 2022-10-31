import logging
import time

from substrateinterface import Keypair
from app.lib.substrate import substrate_batchall_call, substrate_call

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


def transfer_funds(substrate_client, from_account_keypair, target_account_address_list, transfer_amount):
    batch_call = []
    for address in target_account_address_list:
        batch_call.append(substrate_client.compose_call(
            call_module='Balances',
            call_function='transfer',
            call_params={
                'dest': address,
                'value': transfer_amount
                }
            )
        )

    log.info(
        "Sending {} from {} to {}".format(transfer_amount, from_account_keypair.ss58_address, target_account_address_list))
    if len(batch_call) == 1:
        receipt = substrate_call(substrate_client, from_account_keypair, batch_call[0])
    else:
        receipt = substrate_batchall_call(substrate_client, from_account_keypair, batch_call)

    if receipt and receipt.is_success:
        # return new_fund
        return True
    else:
        log.error("Account {} did not receive fund, Extrinsic failed. Error: {}".format(
            target_account_address_list, getattr(receipt, 'error_message', None)))
        return None


def fund_accounts(substrate_client, addresses, funding_account_seed):
    funding_account_keypair = Keypair.create_from_seed(funding_account_seed)
    target_account_address_list = []
    for address in addresses:
        address_funds = get_funds(substrate_client, address)
        log.info('address={} (funds={})'.format(address, address_funds))
        if address_funds < 0.5 * 10 ** 12:  # < 0.5 ROC
            log.info(
                'address={} is not properly funded (funds={}), schedule transferring funds from sudo account'.format(
                    address, address_funds))
            target_account_address_list.append(address)
    transfer_funds(substrate_client, funding_account_keypair, target_account_address_list, 1 * 10**12)
