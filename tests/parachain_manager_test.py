import os
import time
import unittest

from substrateinterface import SubstrateInterface
from testcontainers.compose import DockerCompose
from tests.test_utils import wait_for_http_ready
from app.lib.parachain_manager import get_parachain_head, get_chain_wasm, initialize_parachain, cleanup_parachain, \
    get_parachains_ids, \
    get_parathreads_ids, get_parachain_lifecycles, get_parachain_leases_count


class ParachainManagerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = DockerCompose(os.path.dirname(os.path.abspath(__file__)))
        cls.compose.start()

    @classmethod
    def tearDownClass(cls):
        cls.compose.stop()

    def setUp(self):
        self.compose = ParachainManagerTest.compose
        self.relay_rpc_ws_url = 'ws://172.17.0.1:{}'.format(self.compose.get_service_port("node_alice", 9944))
        self.relay_rpc_http_url = 'http://172.17.0.1:{}'.format(self.compose.get_service_port("node_alice", 9933))
        self.parachain_rpc_ws_url = 'ws://172.17.0.1:{}'.format(self.compose.get_service_port("collator", 9944))
        self.parachain_rpc_http_url = 'http://172.17.0.1:{}'.format(self.compose.get_service_port("collator", 9933))
        wait_for_http_ready(self.relay_rpc_http_url + '/health')
        wait_for_http_ready(self.parachain_rpc_http_url + '/health')
        self.parachain_substrate = SubstrateInterface(url=self.parachain_rpc_ws_url)
        self.relay_substrate = SubstrateInterface(url=self.relay_rpc_ws_url)
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'

    def test_get_parachain_ids(self):
        result = get_parachains_ids(self.relay_substrate)
        print(result)
        self.assertTrue(type(result) is list, 'Get parachain IDs')

    def test_get_parathreads_ids(self):
        result = get_parathreads_ids(self.relay_substrate)
        print(result)
        self.assertTrue(type(result) is list, 'Get parathread IDs')

    def test_get_parachain_lifecycles(self):
        result = get_parachain_lifecycles(self.relay_substrate, 1000)
        print(result)
        self.assertTrue(result is None, 'Parachain is not registered')

    def test_get_chain_wasm(self):
        result = get_chain_wasm(self.parachain_substrate)
        print(result)
        self.assertTrue(result.startswith('0x'), 'Get parachain wasm')

    def test_get_parachain_head(self):
        result = get_parachain_head(self.parachain_substrate)
        print(result)
        self.assertTrue(result.startswith('0x0000'), 'Get parachain head')

    def test_initialize_parachain(self):
        initialize_parachain(self.relay_substrate, self.alice_key, 100, '0x11', '0x11')
        result = get_parachain_lifecycles(self.relay_substrate, 100)
        print(result)
        self.assertTrue(result == "Onboarding", 'Parachain onboarding')

    def test_cleanup_parachain(self):
        initialize_parachain(self.relay_substrate, self.alice_key, 101, '0x11', '0x11')
        for i in range(30):  # wait 5*30 seconds
            if get_parachain_lifecycles(self.relay_substrate, 101) == 'Parachain':
                break
            time.sleep(5)
        cleanup_parachain(self.relay_substrate, self.alice_key, 101)
        result = get_parachain_lifecycles(self.relay_substrate, 101)
        print(result)
        self.assertTrue(result == 'OffboardingParachain', 'Offboarding the Parachain')

    def test_set_force_slot_lease(self):
        para_id = 102
        initialize_parachain(self.relay_substrate, self.alice_key, para_id, '0x11', '0x11', 1)
        leases_count = get_parachain_leases_count(self.relay_substrate, para_id)
        self.assertEqual(leases_count, 1, 'Slot lease set')


if __name__ == '__main__':
    unittest.main()
