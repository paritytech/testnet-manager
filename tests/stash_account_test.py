import unittest

from testcontainers.core.container import DockerContainer
from substrateinterface import Keypair

from app.lib.stash_accounts import get_account_funds
from tests.test_utils import wait_for_http_ready


class StashAccountTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command('--dev --validator --unsafe-rpc-external --rpc-methods=unsafe  --rpc-cors=all')
        self.polkadot.with_exposed_ports(9944)
        self.polkadot.start()

        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')

    def tearDown(self):
        self.polkadot.stop()

    def test_get_account_funds(self):
        alice_key = Keypair.create_from_uri("//Alice")
        alice_funds = get_account_funds(self.polkadot_rpc_ws_url, alice_key.ss58_address)
        self.assertEqual(alice_funds, 10000000000000000, "Alice's funds successfully retrieved")

if __name__ == '__main__':
    unittest.main()
