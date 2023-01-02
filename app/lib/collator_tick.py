import logging
import traceback

from app.lib.collator_account import get_derived_collator_keypair
from app.lib.node_utils import inject_key
from app.lib.substrate import get_node_client

log = logging.getLogger('collator_tick')


# tick supports only invulnerable (collators should be in chainspec)
def register_tick_collator(node_name):
    try:
        node_client = get_node_client(node_name)
        collator_keypair = get_derived_collator_keypair(node_name)
        inject_key(node_client, collator_keypair)
        return collator_keypair.ss58_address

    except Exception as e:
        log.error("Unable to register_tick_collator. Error: {}, stacktrace:\n".format(e, traceback.print_exc()))
        return None
