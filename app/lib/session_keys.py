import logging
import requests
from substrateinterface import Keypair
from app.lib.substrate import get_substrate_client, substrate_call

log = logging.getLogger('session_keys')


# substrate_client must be connected to the node on which we want to run rotate_keys
def rotate_node_session_keys(node_http_endpoint):
    try:
        rotate_keys = requests.post(node_http_endpoint,
                                    data='{"id":1, "jsonrpc":"2.0", "method": "author_rotateKeys", "params":[]}',
                                    headers={'Content-type': 'application/json'})
        if rotate_keys.status_code == 200:
            log.info("{} session keys rotated successfully".format(node_http_endpoint))
            return rotate_keys.json()['result']
        else:
            return ''
    except Exception as err:
        log.error("Failed to rotate key on {}; Error: {}".format(node_http_endpoint, err))
        return ''


def decode_session_key(substrate_client, session_key):
    # decode session_key see: https://github.com/polkascan/py-substrate-interface/issues/205
    type_id = substrate_client.get_metadata_call_function('Session', 'set_keys')['fields'][0]['type']
    return substrate_client.decode_scale("scale_info::{}".format(type_id), session_key)


# stash keypair account must have some funds
def set_node_session_key(ws_endpoint, stash_seed, session_key):
    substrate_client = get_substrate_client(ws_endpoint)

    if type(session_key) == str:
        session_key = decode_session_key(substrate_client, session_key)

    keypair = Keypair.create_from_uri(stash_seed)
    call = substrate_client.compose_call(
        call_module='Session',
        call_function='set_keys',
        call_params={
            'keys': session_key,
            'proof': 'None'
        }
    )
    result = substrate_call(substrate_client, keypair, call, wait=True)
    if result and result.is_success:
        return True
    else:
        return False


def get_queued_keys(substrate_client):
    try:
        queued_keys = substrate_client.query(
            module='Session',
            storage_function='QueuedKeys',
            params=[]
        )
        return dict(queued_keys.value)
    except Exception as err:
        log.error(err)
        return {}
