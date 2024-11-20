import time
import unittest

from testcontainers.core.container import DockerContainer

from app.lib.session_keys import rotate_node_session_keys, set_node_session_key
from tests.test_constants import RPC_DEV_FLAGS
from tests.test_utils import wait_for_http_ready


class NodeSessionKeysTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command(f'--dev --validator --insecure-validator-i-know-what-i-do {RPC_DEV_FLAGS}')
        self.polkadot.with_exposed_ports(9944)
        self.polkadot.start()
        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')

    def tearDown(self):
        self.polkadot.stop()

    def test_rotate_node_session_keys(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        self.assertTrue(session_key, "Rotate key executed successfully on the node")

    def test_set_node_session_keys(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        result = set_node_session_key(self.polkadot_rpc_ws_url, '//Alice//stash', session_key)
        print(result)
        self.assertTrue(result, 'SetKeys executed successfully on //Alice//stash')

    def test_rotate_node_session_keys_bad_url(self):
        session_key = rotate_node_session_keys('http://localhost:1234')
        self.assertFalse(session_key, "Rotate key correctly fails on bad URL")

    def test_set_node_session_keys_bad_account(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        self.assertFalse(set_node_session_key(self.polkadot_rpc_ws_url, '//Alice/Iamnotafundedaccount', session_key),
                         'SetKeys correctly fails on an account without funds')

if __name__ == '__main__':
    unittest.main()
