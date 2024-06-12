import time
import unittest

from testcontainers.core.container import DockerContainer
from os import environ

from app.lib.node_utils import is_node_ready, get_node_health, is_node_ready_ws, get_node_version, \
    get_node_sync_state
from app.lib.substrate import get_substrate_client, substrate_rpc_request
from tests.test_constants import RPC_DEV_FLAGS
from tests.test_utils import wait_for_http_ready


class NodeUtilsTest(unittest.TestCase):

    def setUp(self):
        self.polkadot = DockerContainer('parity/polkadot:latest')
        self.polkadot.with_command(f'--dev --validator --node-key 4b067400ba508d783ccf86b73aa825ebafea96c95ebdff3f307ab6dd854f0852 {RPC_DEV_FLAGS}')
        self.polkadot.with_exposed_ports(9944)
        self.polkadot.start()
        self.polkadot_rpc_http_url = 'http://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        self.polkadot_rpc_ws_url = 'ws://{}:{}'.format(self.polkadot.get_container_host_ip(), self.polkadot.get_exposed_port(9944))
        wait_for_http_ready(self.polkadot_rpc_http_url + '/health')
        time.sleep(10)
        self.polkadot_node_client = get_substrate_client(self.polkadot_rpc_ws_url)

        # Set test execution environment
        environ.setdefault('NAMESPACE', 'polkadot')
        environ.setdefault('HEALTHY_MIN_PEER_COUNT', '0')

    def tearDown(self):
        self.polkadot.stop()

    def test_get_node_health(self):
        health = get_node_health(self.polkadot_rpc_http_url)
        self.assertEqual(health.status_code, 200, "Successfully retrieved node health")

    def test_is_node_ready(self):
        node_ready = is_node_ready(self.polkadot_rpc_http_url)
        self.assertTrue(node_ready, "Successfully retrieved node readiness")

    def test_is_node_ready_ws(self):
        node_ready = is_node_ready_ws(self.polkadot_node_client)
        self.assertTrue(node_ready, "Successfully retrieved node readiness")

    def test_get_node_peer_id(self):
        node_peer_id = substrate_rpc_request(self.polkadot_node_client, "system_localPeerId")
        self.assertEqual(node_peer_id, '12D3KooWMddYZctYE6RePcxvEWvU1Xyq5X4x7WW6FK4GjVF8QvFt', "Successfully retrieved peer ID")

    def test_get_node_version(self):
        node_binary_version = self.polkadot.exec("polkadot --version").output.decode("utf-8")
        node_rpc_version = get_node_version(self.polkadot_node_client)
        self.assertTrue(node_rpc_version in node_binary_version, "Successfully retrieved node version")

    def test_get_node_sync_state(self):
        node_sync_state = get_node_sync_state(self.polkadot_node_client)
        self.assertEqual(node_sync_state['startingBlock'], 0, "Successfully retrieved node sync starting block")
        self.assertTrue(node_sync_state['currentBlock'] >= 0, "Successfully retrieved node sync current block")


if __name__ == '__main__':
    unittest.main()
