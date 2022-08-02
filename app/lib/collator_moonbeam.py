import logging

from substrateinterface import Keypair, KeypairType
from hashlib import blake2b
from app.lib.substrate import substrate_call
from app.lib.balance_utils import transfer_funds
from app.lib.substrate import get_node_client
from app.config.network_configuration import network_validators_root_seed

log = logging.getLogger('collator_moonbeam')


def get_moon_node_collator_uri(root_seed, node_name):
    statefulset = "-".join(node_name.split('-')[0:-1])
    # this hash function may have collision, if you have more than 100 statefulset, replace it.
    statefulset_hash = int(blake2b(statefulset.encode(), digest_size=3).digest().hex(), 16)
    pod_number = node_name.split('-')[-1]
    return f"{root_seed}/m/44'/60'/0'/{statefulset_hash}/{pod_number}"


def get_moon_root_uri(root_seed):
    return f"{root_seed}/m/44'/60'/0'/0/0"


def get_moon_keypair_from_uri(uri):
    return Keypair.create_from_uri(uri, crypto_type=KeypairType.ECDSA)


def register_moon_collator(node_name, rotate_key=False):
    try:
        # init
        node_client = get_node_client(node_name)
        collator_root_seed = network_validators_root_seed()
        rich_key_uri = get_moon_root_uri(collator_root_seed)
        collator_key_uri = get_moon_node_collator_uri(collator_root_seed, node_name)
        keypair = Keypair.create_from_uri(collator_key_uri, crypto_type=KeypairType.ECDSA)
        keypair_rich = Keypair.create_from_uri(rich_key_uri, crypto_type=KeypairType.ECDSA)
        node_client.init_runtime()
        node_client.runtime_config.update_type_registry({
            "types": {
                "Address": "H160",
                "LookupSource": "H160",
                "AccountId": "H160",
                "ExtrinsicSignature": "EcdsaSignature",
            }
        })

        # Transfer money
        account_info = node_client.query('System', 'Account', params=[keypair.ss58_address])
        if account_info.value['data']['free'] < 1101 * 10 ** 18:
            log.info("Funding {}".format(keypair.ss58_address))
            # 1000 bound, 100 security deposit, 1 tx fee
            transfer_funds(node_client, keypair_rich, keypair.ss58_address, 1101 * 10 ** 18)


        # Join the Candidate Pool
        candidate_pool = node_client.query('ParachainStaking', 'CandidatePool', params=[]).value
        if not any(d['owner'].lower() == keypair.ss58_address.lower() for d in candidate_pool):
            log.info("Joining the Candidate Pool {}".format(keypair.ss58_address))
            call = node_client.compose_call(
                call_module='ParachainStaking',
                call_function='join_candidates',
                call_params={
                    'bond': 1000 * 10 ** 18,
                    'candidate_count': len(candidate_pool)
                }
            )
            # wait=False since endpoint is http not ws
            substrate_call(node_client, keypair, call, wait=False)

        # Mapping Extrinsic
        author_mapping = node_client.query_map('AuthorMapping', 'MappingWithDeposit')
        if not any(d.value['account'].lower() == keypair.ss58_address.lower() for a, d in author_mapping) or rotate_key:
            session_key = node_client.rpc_request(method="author_rotateKeys", params=[])
            log.info("Session key: {}".format(session_key['result']))

            call = node_client.compose_call(
                call_module='AuthorMapping',
                call_function='add_association',
                call_params={
                    'author_id': session_key['result'],
                }
            )
            # wait=False since endpoint is http not ws
            substrate_call(node_client, keypair, call, wait=False)

        return keypair.ss58_address

    except Exception as e:
        log.error("Unable to register_moon_collator. Error: {}".format(e))
        return None
