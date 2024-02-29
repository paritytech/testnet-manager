import time
import unittest

from testcontainers.core.container import DockerContainer
from substrateinterface import Keypair


from app.lib.substrate import get_substrate_client, get_sudo_keys, substrate_call, substrate_proxy_call, substrate_check_sudo_key_and_call
from app.lib.balance_utils import get_funds
from tests.test_utils import wait_for_http_ready


class SubstrateTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command('--dev --validator --unsafe-rpc-external --rpc-methods=unsafe  --rpc-cors=all')
        self.polkadot.with_exposed_ports(9944)
        self.polkadot.start()
        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')
        time.sleep(10)
        self.polkadot_node_client = get_substrate_client(self.polkadot_rpc_ws_url)
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'
        self.alice_key_address = '5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY'
        self.alice_keypair = Keypair.create_from_seed(self.alice_key)

    def tearDown(self):
        self.polkadot.stop()

    def helper_add_proxy(self, delegate):
        call = self.polkadot_node_client.compose_call(
            call_module='Proxy',
            call_function='add_proxy',
            call_params={
                'delegate': delegate,
                'proxy_type': 'Any',
                'delay': 0
            }
        )
        substrate_call(self.polkadot_node_client, self.alice_keypair, call, True)

    # test call which needs sudo
    def helper_test_call(self, who, new_free):
        payload = self.polkadot_node_client.compose_call(
                call_module='Balances',
                call_function='force_set_balance',
                call_params={
                    'who': who,
                    'new_free': new_free,
                }
            )
        return self.polkadot_node_client.compose_call(
                call_module='Sudo',
                call_function='sudo',
                call_params={'call': payload.value}
            )

    def test_substrate_proxy_call(self):
        proxy_keypair = Keypair.create_from_uri('//Bob')
        test_key = Keypair.create_from_uri('//Test-key-1').ss58_address
        self.helper_add_proxy(proxy_keypair.ss58_address)
        set_funds = 99998888
        payload = self.helper_test_call(test_key, set_funds)
        substrate_proxy_call(self.polkadot_node_client, proxy_keypair, self.alice_key_address, payload, True)

        new_funds = get_funds(self.polkadot_node_client, test_key)
        print(new_funds)
        self.assertEqual(set_funds, new_funds, "Successfully run proxy call")

    def test_get_sudo_keys_1(self):
        sudo = get_sudo_keys(self.polkadot_node_client)
        print(sudo)
        self.assertEqual(sudo['sudo'], self.alice_key_address, "Successfully retrieved sudo keys")

    def test_get_sudo_keys_2(self):
        proxy_key = Keypair.create_from_uri('//Charlie').ss58_address
        self.helper_add_proxy(proxy_key)
        sudo = get_sudo_keys(self.polkadot_node_client)
        print(sudo)
        self.assertTrue(proxy_key in sudo['proxies'], "Successfully retrieved proxies keys")

    # use sudo account  to call
    def test_substrate_check_sudo_key_and_call_1(self):
        test_key = Keypair.create_from_uri('//Test-key-2').ss58_address
        set_funds = 99997777
        payload = self.helper_test_call(test_key, set_funds)
        substrate_check_sudo_key_and_call(self.polkadot_node_client, self.alice_keypair, payload, True)
        new_funds = get_funds(self.polkadot_node_client, test_key)
        print(new_funds)
        self.assertEqual(set_funds, new_funds, "Successfully run proxy call")

    # use sudo proxy account to call
    def test_substrate_check_sudo_key_and_call_2(self):
        proxy_keypair = Keypair.create_from_uri('//Dave')
        test_key = Keypair.create_from_uri('//Test-key-3').ss58_address
        self.helper_add_proxy(proxy_keypair.ss58_address)
        set_funds = 99996666
        payload = self.helper_test_call(test_key, set_funds)
        substrate_check_sudo_key_and_call(self.polkadot_node_client, proxy_keypair, payload, True)

        new_funds = get_funds(self.polkadot_node_client, test_key)
        print(new_funds)
        self.assertEqual(set_funds, new_funds, "Successfully run proxy call")

    # use any account to call, should fail
    def test_substrate_check_sudo_key_and_call_3(self):
        keypair = Keypair.create_from_uri('//Eve')
        test_key = Keypair.create_from_uri('//Test-key-4').ss58_address
        payload = self.helper_test_call(test_key, 99995555)
        result = substrate_check_sudo_key_and_call(self.polkadot_node_client, keypair, payload, True)
        self.assertEqual(result, None, "Successfully run proxy call")


if __name__ == '__main__':
    unittest.main()
