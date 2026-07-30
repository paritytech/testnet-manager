import time
import unittest

from substrateinterface import Keypair
from testcontainers.core.container import DockerContainer

from app.lib.session_keys import rotate_node_session_keys, set_node_session_key
from tests.test_constants import RPC_DEV_FLAGS
from tests.test_utils import wait_for_http_ready


def _owner(stash_seed):
    return '0x' + Keypair.create_from_uri(stash_seed).public_key.hex()


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
        rotated = rotate_node_session_keys(self.polkadot_rpc_http_url, owner=_owner('//Alice//stash'))
        self.assertTrue(rotated, "Rotate key executed successfully on the node")
        self.assertTrue(rotated['keys'], "Rotate returned session keys")
        # Recent binaries return an ownership proof; older ones fall back to '0x'.
        self.assertTrue(rotated['proof'], "Rotate returned a proof (or the '0x' fallback)")

    def test_set_node_session_keys(self):
        rotated = rotate_node_session_keys(self.polkadot_rpc_http_url, owner=_owner('//Alice//stash'))
        result = set_node_session_key(self.polkadot_rpc_ws_url, '//Alice//stash',
                                      rotated['keys'], proof=rotated['proof'])
        print(result)
        self.assertTrue(result, 'SetKeys executed successfully on //Alice//stash')

    def test_rotate_node_session_keys_bad_url(self):
        session_key = rotate_node_session_keys('http://localhost:1234', owner=_owner('//Alice//stash'))
        self.assertFalse(session_key, "Rotate key correctly fails on bad URL")

    def test_set_node_session_keys_bad_account(self):
        bad_seed = '//Alice/Iamnotafundedaccount'
        rotated = rotate_node_session_keys(self.polkadot_rpc_http_url, owner=_owner(bad_seed))
        self.assertFalse(set_node_session_key(self.polkadot_rpc_ws_url, bad_seed,
                                              rotated['keys'], proof=rotated['proof']),
                         'SetKeys correctly fails on an account without funds')

if __name__ == '__main__':
    unittest.main()
