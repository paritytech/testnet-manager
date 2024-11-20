import unittest, os

from testcontainers.core.container import DockerContainer
from substrateinterface import Keypair
from app.lib.substrate import get_substrate_client
from app.lib.validator_manager import get_validator_set, setup_pos_validator, get_validators_pending_addition, staking_chill, \
    get_validators_pending_deletion
from tests.test_constants import RPC_DEV_FLAGS
from tests.test_utils import wait_for_http_ready
from unittest import mock


@mock.patch.dict(os.environ, {"RELAY_CHAIN_CONSENSUS": "pos"})
class ValidatorManagerTestPoS(unittest.TestCase):

    def setUp(self):
        # Start Alice validator
        self.alice_validator = DockerContainer('parity/polkadot:latest')
        self.alice_validator.with_command(f'--chain westend-local --validator --unsafe-force-node-key-generation --alice {RPC_DEV_FLAGS}')
        self.alice_validator.with_exposed_ports(9944, 10333)
        self.alice_validator.start()

        self.alice_validator_rpc_ws_url = f'ws://{self.alice_validator.get_container_host_ip()}:{self.alice_validator.get_exposed_port(9944)}'

        # Start Bob validator and connect it to Alice
        self.bob_validator = DockerContainer('parity/polkadot:latest')
        self.bob_validator.with_command(f'-chain westend-local --validator --unsafe-force-node-key-generation --bob --unsafe-rpc-external {RPC_DEV_FLAGS} --bootnodes /ip4/127.0.0.1/tcp/{self.alice_validator.get_exposed_port(10333)}/p2p/12D3KooWAvdwXzjmRpkHpz8PzUTaX1o23SdpgAWVyTGMSQ68QXK6')
        self.bob_validator.with_exposed_ports(9944)
        self.bob_validator.start()
        self.bob_validator_http_url = f'http://{self.bob_validator.get_container_host_ip()}:{self.bob_validator.get_exposed_port(9944)}'
        self.bob_validator_rpc_ws_url = f'ws://{self.bob_validator.get_container_host_ip()}:{self.bob_validator.get_exposed_port(9944)}'
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'

        wait_for_http_ready(self.bob_validator_http_url + '/health')

    def tearDown(self):
        self.alice_validator.stop()
        self.bob_validator.stop()

    def test_get_pos_validator_set(self):
        validator_set = get_validator_set(self.bob_validator_rpc_ws_url)
        print(validator_set)
        self.assertTrue(validator_set, 'Validator set is present on the chain')

    def test_register_pos_validator(self):
        charlie_stash = Keypair.create_from_uri('//Charlie//stash', ss58_format=42)
        substrate_client = get_substrate_client(self.alice_validator_rpc_ws_url)
        session_key = substrate_client.rpc_request(method="author_rotateKeys", params=[])['result']
        setup_pos_validator(self.alice_validator_rpc_ws_url, "//Charlie//stash", session_key, "//Charlie")
        validators_to_add = get_validators_pending_addition(self.alice_validator_rpc_ws_url)
        print(validators_to_add)
        self.assertEqual(validators_to_add, [charlie_stash.ss58_address], "Registered validator address successfully added to validators_to_add")

    def test_deregister_pos_validator(self):
        bob_stash = Keypair.create_from_uri("//Bob//stash", ss58_format=42)
        staking_chill(self.alice_validator_rpc_ws_url, "//Bob//stash")
        validators_to_retire = get_validators_pending_deletion(self.alice_validator_rpc_ws_url)
        print(validators_to_retire)
        self.assertEqual(validators_to_retire, [bob_stash.ss58_address], "Deregistered validator address successfully added to validators_to_retire")


if __name__ == '__main__':
    unittest.main()
