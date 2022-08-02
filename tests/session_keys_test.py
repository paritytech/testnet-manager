import time
import unittest

from testcontainers.core.container import DockerContainer

from app.lib.session_keys import rotate_node_session_keys, set_node_session_key
from tests.test_utils import wait_for_http_ready


class NodeSessionKeysTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command('--dev --validator --unsafe-rpc-external --unsafe-ws-external --rpc-methods=unsafe  --rpc-cors=all')
        self.polkadot.with_exposed_ports(9933,9944)
        self.polkadot.start()
        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9933))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')

    def tearDown(self):
        self.polkadot.stop()

    def test_rotate_node_session_keys(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        self.assertTrue(session_key, "Rotate key executed successfully on the node")

    def test_set_node_session_keys(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        self.assertTrue(set_node_session_key(self.polkadot_rpc_ws_url, '//Alice', session_key),
                        'SetKeys executed successfully on //Alice')

    def test_rotate_node_session_keys_bad_url(self):
        session_key = rotate_node_session_keys('http://localhost:1234')
        self.assertFalse(session_key, "Rotate key correctly fails on bad URL")

    def test_set_node_session_keys_bad_account(self):
        session_key = rotate_node_session_keys(self.polkadot_rpc_http_url)
        self.assertFalse(set_node_session_key(self.polkadot_rpc_ws_url, '//Alice/Iamnotafundedaccount', session_key),
                         'SetKeys correctly fails on an account without funds')

if __name__ == '__main__':
    unittest.main()
