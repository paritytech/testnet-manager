import datetime
import unittest

from testcontainers.core.container import DockerContainer
from substrateinterface import SubstrateInterface, Keypair

from app.lib.balance_utils import get_funds, transfer_funds, fund_accounts, teleport_funds
from tests.test_utils import wait_for_http_ready


class BalanceUtilsTest(unittest.TestCase):

    def setUp(self):
        # Start Alice validator
        self.alice_validator = DockerContainer('parity/polkadot:latest')
        self.alice_validator.with_command('--chain rococo-local --validator --alice --unsafe-ws-external --rpc-cors=all')
        self.alice_validator.with_exposed_ports(9944)
        self.alice_validator.start()
        self.alice_validator_rpc_ws_url = 'ws://{}:{}'.format(self.alice_validator.get_container_host_ip(),
                                                              self.alice_validator.get_exposed_port(9944))

        # Start Bob validator
        self.bob_validator = DockerContainer('parity/polkadot:latest')
        self.bob_validator.with_command('--chain rococo-local --validator --bob --unsafe-rpc-external --rpc-cors=all')
        self.bob_validator.with_exposed_ports(9933)
        self.bob_validator.start()
        self.bob_validator_http_url = 'http://{}:{}'.format(self.bob_validator.get_container_host_ip(),
                                                            self.bob_validator.get_exposed_port(9933))
        # prepare keys
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'
        self.alice_key_address = '5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY'
        self.test_key_0_address = '5Gpg3hhPkyPRSwQc5EYprccoJ81fzEdUQqbtsY25RMezaPjb'
        self.test_key_1_address = '5DMCAnbTJWDbB1bb91RCTmY5t9Ngie2m3LCakb2stmYUyByY'
        self.test_key_2_address = '5GTn6hXhzRoEkEqWfJarWnjfVMMKcvzRrR85vhAxJmwepwbB'
        self.test_key_3_address = '5G672AgoojLfkZyN8LkTqrGwwjM3ZsGhmg5t9DkUzFmaLeUN'
        wait_for_http_ready(self.bob_validator_http_url + '/health')
        self.substrate_client = SubstrateInterface(url=self.alice_validator_rpc_ws_url)

    def tearDown(self):
        self.alice_validator.stop()
        self.bob_validator.stop()

    def test_get_funds(self):
        alice_keypair = Keypair.create_from_seed(self.alice_key)
        funds = get_funds(self.substrate_client, alice_keypair.ss58_address)
        print(funds)
        self.assertEqual(funds, 1000000000000000000, 'Alice account have {} token'.format(funds))

    def test_transfer_funds(self):
        alice_keypair = Keypair.create_from_seed(self.alice_key)
        new_fund = transfer_funds(self.substrate_client, alice_keypair, [self.test_key_0_address], 1000000000000)
        print("new_fund", new_fund)
        funds = get_funds(self.substrate_client, self.test_key_0_address)
        print("funds", funds)
        self.assertEqual(funds, 1000000000000, 'Alice account have {} token'.format(funds))

    def test_teleport_funds(self):
        alice_keypair = Keypair.create_from_seed(self.alice_key)
        alice_funds_before_teleport = get_funds(self.substrate_client, alice_keypair.ss58_address)
        teleport_amount = 10000000000000000
        teleport_funds(self.substrate_client, alice_keypair, 1000, [self.test_key_0_address], 10000000000000000)
        alice_funds_after_teleport = get_funds(self.substrate_client, alice_keypair.ss58_address)
        self.assertLess(alice_funds_after_teleport, alice_funds_before_teleport - teleport_amount, 'Alice account have {} been teleported')

    def test_fund_accounts(self):
        print(datetime.datetime.now())
        fund_accounts(
            self.substrate_client,
            [self.test_key_1_address, self.test_key_2_address, self.test_key_3_address],
            self.alice_key
        )
        print(datetime.datetime.now())
        fund1 = get_funds(self.substrate_client, self.test_key_1_address)
        fund2 = get_funds(self.substrate_client, self.test_key_2_address)

        print(fund1, fund2)
        self.assertEqual(fund1, fund2, 'Alice account have {} token'.format(fund1))


if __name__ == '__main__':
    unittest.main()
