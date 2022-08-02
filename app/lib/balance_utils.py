import logging
import time

from substrateinterface import Keypair

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


def transfer_funds(substrate_client, from_account_keypair, target_account_address, transfer_amount):
    call = substrate_client.compose_call(
        call_module='Balances',
        call_function='transfer',
        call_params={
            'dest': target_account_address,
            'value': transfer_amount
        }
    )

    extrinsic = substrate_client.create_signed_extrinsic(
        call=call,
        keypair=from_account_keypair
    )

    try:
        old_balance = substrate_client.query('System', 'Account', params=[target_account_address]).value['data']['free']
        log.info("Sending {} from {} to {}".format(transfer_amount, from_account_keypair.ss58_address, target_account_address))
        receipt = substrate_client.submit_extrinsic(extrinsic, wait_for_inclusion=False)
        log.info("Extrinsic '{}' sent".format(receipt.extrinsic_hash))
        # todo: set wait_for_inclusion=False in submit_extrinsic after endpoint replaced to ws, and remove this wait.
        # wait until balance changed
        for i in range(30):
            time.sleep(2)
            new_fund = substrate_client.query('System', 'Account', params=[target_account_address]).value['data']['free']
            if new_fund > old_balance:
                log.info("New fund: {}".format(new_fund))
                return new_fund
        # timeout
        log.error("Account {} did not receive fund, balance: {}. Error: Timeout".format(target_account_address, new_fund))
        return new_fund

    except Exception as e:
        log.error("Failed to send fund from {} to {}. Error: {}".format(from_account_keypair.ss58_address,
                                                                        target_account_address, e))
        return None


def fund_accounts(substrate_client, addresses, funding_account_seed):
    funding_account_keypair = Keypair.create_from_seed(funding_account_seed)
    for address in addresses:
        address_funds = get_funds(substrate_client, address)
        log.info('address={} (funds={})'.format(address, address_funds))
        if address_funds < 0.5 * 10 ** 12:  # < 0.5 ROC
            log.info(
                'address={} is not properly funded (funds={}), transferring funds from sudo account'.format(
                    address, address_funds))
            transfer_funds(substrate_client, funding_account_keypair, address, 1 * 10**12)
