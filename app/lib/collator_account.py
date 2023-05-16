import logging
import traceback

from substrateinterface import Keypair, KeypairType
from hashlib import blake2b

from app.config.network_configuration import network_root_seed
from app.lib.substrate import get_node_client

log = logging.getLogger(__name__)

def get_derived_collator_seed(node_name):
    root_seed = network_root_seed()
    return root_seed + "//collator//" + node_name


def get_derived_collator_keypair(node_name, ss58_format=42):
    return Keypair.create_from_uri(get_derived_collator_seed(node_name), ss58_format=int(ss58_format), crypto_type=KeypairType.SR25519)


def get_derived_collator_account(node_name, ss58_format=42):
    return get_derived_collator_keypair(node_name, ss58_format).ss58_address


def get_derived_collator_session_keys(node_name):
    try:
        node_client = get_node_client(node_name)
        seed = get_derived_collator_seed(node_name)
        hex = node_client.runtime_call("SessionKeys", "generate_session_keys", [seed]).value
        return {
            'aura': hex
        }
    except Exception as e:
        log.error("Unable to get_derived_collator_session_keys. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None


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


def get_derived_moon_collator_account(node_name):
    key_seed = network_root_seed()
    keypair = get_moon_keypair_from_uri(get_moon_node_collator_uri(key_seed, node_name))
    return keypair.ss58_address
