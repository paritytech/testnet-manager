import logging
import traceback

from substrateinterface import Keypair
from app.lib.substrate import get_node_client
from app.config.network_configuration import network_validators_root_seed
from app.lib.node_utils import inject_key

log = logging.getLogger('collator_tick')


# tick supports only invulnerable (collators should be in chainspec)
def register_tick_collator(node_name):
    try:
        node_client = get_node_client(node_name)
        collator_root_seed = network_validators_root_seed()
        collator_aura_key = collator_root_seed + "//collator//" + node_name
        keypair = Keypair.create_from_uri(collator_aura_key)
        inject_key(node_client, collator_aura_key)
        return keypair.ss58_address

    except Exception as e:
        log.error("Unable to register_tick_collator. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None
