import unittest

from testcontainers.core.container import DockerContainer
from substrateinterface import Keypair

from app.lib.stash_accounts import get_account_funds, fund_account
from tests.test_utils import wait_for_http_ready


class StashAccountTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command('--dev --validator --unsafe-rpc-external --unsafe-ws-external --rpc-methods=unsafe  --rpc-cors=all')
        self.polkadot.with_exposed_ports(9933, 9944)
        self.polkadot.start()

        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9933))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')

    def tearDown(self):
        self.polkadot.stop()

    def test_get_account_funds(self):
        alice_key = Keypair.create_from_uri("//Alice")
        alice_funds = get_account_funds(self.polkadot_rpc_ws_url, alice_key.ss58_address)
        self.assertEqual(alice_funds, 10000000000000000, "Alice's funds successfully retrieved")

    def test_fund_stash_account_from_sudo(self):
        alice_key = Keypair.create_from_uri("//Alice")
        stash_account = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
        fund_account(self.polkadot_rpc_ws_url, self.alice_key, stash_account.ss58_address)

        alice_funds = get_account_funds(self.polkadot_rpc_ws_url, alice_key.ss58_address)
        stash_account_funds = get_account_funds(self.polkadot_rpc_ws_url, stash_account.ss58_address)
        self.assertLess(alice_funds, 99990000000000000, "Alice's funds successfully transfered out")
        self.assertEqual(stash_account_funds, 10000000000, "Stash account's funds successfully transfered in")

if __name__ == '__main__':
    unittest.main()
