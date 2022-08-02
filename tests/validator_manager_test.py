import unittest

from testcontainers.core.container import DockerContainer
from substrateinterface import Keypair

from app.lib.validator_manager import get_validator_set, register_validators, get_validators_to_add, deregister_validators, \
    get_validators_to_retire
from tests.test_utils import wait_for_http_ready


class ValidatorManagerTest(unittest.TestCase):

    def setUp(self):
        # Start Alice validator
        self.alice_validator = DockerContainer('parity/polkadot:latest')
        self.alice_validator.with_command('--chain rococo-local --validator --alice --unsafe-ws-external --rpc-cors=all')
        self.alice_validator.with_exposed_ports(9944, 10333)
        self.alice_validator.start()

        self.alice_validator_rpc_ws_url = 'ws://{}:{}'.format(self.alice_validator.get_container_host_ip(),
                                                              self.alice_validator.get_exposed_port(9944))

        # Start Bob validator and connect it to Alice
        self.bob_validator = DockerContainer('parity/polkadot:latest')
        self.bob_validator.with_command("""
            --chain rococo-local --validator --bob --unsafe-ws-external --rpc-cors=all \
            --bootnodes /ip4/127.0.0.1/tcp/{}/p2p/12D3KooWAvdwXzjmRpkHpz8PzUTaX1o23SdpgAWVyTGMSQ68QXK6
        """.format(self.alice_validator.get_exposed_port(10333)))
        self.bob_validator.with_exposed_ports(9933, 9944)
        self.bob_validator.start()
        self.bob_validator_http_url = 'http://{}:{}'.format(self.bob_validator.get_container_host_ip(),
                                                            self.bob_validator.get_exposed_port(9933))
        self.bob_validator_rpc_ws_url = 'ws://{}:{}'.format(self.bob_validator.get_container_host_ip(),
                                                            self.bob_validator.get_exposed_port(9944))
        self.alice_key = '0xe5be9a5092b81bca64be81d212e7f2f9eba183bb7a90954f7b76361f6edb5c0a'

        wait_for_http_ready(self.bob_validator_http_url + '/health')


    def tearDown(self):
        self.alice_validator.stop()
        self.bob_validator.stop()

    def test_get_validator_set(self):
        validator_set = get_validator_set(self.bob_validator_rpc_ws_url)
        self.assertTrue(validator_set, 'Validator set is present on the chain')
        print(validator_set)

    def test_register_validator(self):
        charlie_key = Keypair.create_from_uri('//Charlie', ss58_format=42)
        register_validators(self.alice_validator_rpc_ws_url, self.alice_key, [charlie_key.ss58_address])
        validators_to_add = get_validators_to_add(self.alice_validator_rpc_ws_url)
        self.assertEqual(validators_to_add, [charlie_key.ss58_address], "Registered validator address successfully added to validators_to_add")
        print(validators_to_add)

    def test_deregister_validator(self):
        bob_key = Keypair.create_from_uri('//Bob', ss58_format=42)
        deregister_validators(self.alice_validator_rpc_ws_url, self.alice_key, [bob_key.ss58_address])
        validators_to_retire = get_validators_to_retire(self.alice_validator_rpc_ws_url)
        self.assertEqual(validators_to_retire, [bob_key.ss58_address], "Deregistered validator address successfully added to validators_to_retire")
        print(validators_to_retire)


if __name__ == '__main__':
    unittest.main()
