import logging
import requests
from substrateinterface import Keypair
from app.lib.substrate import get_substrate_client, substrate_call

log = logging.getLogger('session_keys')


# substrate_client must be connected to the node on which we want to run rotate_keys
def rotate_node_session_keys(node_http_endpoint, owner=None):
    """Rotate the node's session keys.

    When `owner` (the hex-encoded stash account id) is given, call
    `author_rotateKeysWithOwner` so the node also returns a `proof` of key
    ownership. Runtimes carrying polkadot-sdk#1739 verify this proof in
    `session.set_keys` and reject an empty one with `InvalidProof`. Nodes
    whose binary predates that RPC (and runtimes that don't require a proof)
    are handled by falling back to plain `author_rotateKeys`.

    Returns `{'keys': '0x..', 'proof': '0x..'}` (proof is `'0x'` when the
    chain/binary doesn't produce one), or `''` on failure.
    """
    try:
        if owner:
            req = {"id": 1, "jsonrpc": "2.0",
                   "method": "author_rotateKeysWithOwner", "params": [owner]}
        else:
            req = {"id": 1, "jsonrpc": "2.0", "method": "author_rotateKeys", "params": []}
        rotate_keys = requests.post(node_http_endpoint, json=req,
                                    headers={'Content-type': 'application/json'}, timeout=10)
        if rotate_keys.status_code != 200:
            return ''
        body = rotate_keys.json()
        if 'error' in body:
            # -32601 = "Method not found": the node binary predates
            # `author_rotateKeysWithOwner`, retry with the legacy RPC.
            if owner and body['error'].get('code') == -32601:
                log.warning("{} lacks author_rotateKeysWithOwner, falling back to "
                            "author_rotateKeys (no ownership proof)".format(node_http_endpoint))
                return rotate_node_session_keys(node_http_endpoint, owner=None)
            log.error("Failed to rotate key on {}; RPC error: {}".format(node_http_endpoint, body['error']))
            return ''
        result = body['result']
        log.info("{} session keys rotated successfully".format(node_http_endpoint))
        # `author_rotateKeysWithOwner` returns {keys, proof}; `author_rotateKeys`
        # returns the keys blob directly.
        if isinstance(result, dict):
            return {'keys': result['keys'], 'proof': result.get('proof') or '0x'}
        return {'keys': result, 'proof': '0x'}
    except Exception as err:
        log.error("Failed to rotate key on {}; Error: {}".format(node_http_endpoint, err))
        return ''


def decode_session_key(substrate_client, session_key):
    # decode session_key see: https://github.com/polkascan/py-substrate-interface/issues/205
    type_id = substrate_client.get_metadata_call_function('Session', 'set_keys')['fields'][0]['type']
    return substrate_client.decode_scale("scale_info::{}".format(type_id), session_key)


# stash keypair account must have some funds
def set_node_session_key(ws_endpoint, stash_seed, session_key, proof='0x'):
    substrate_client = get_substrate_client(ws_endpoint)

    if type(session_key) == str:
        session_key = decode_session_key(substrate_client, session_key)

    keypair = Keypair.create_from_uri(stash_seed)
    call = substrate_client.compose_call(
        call_module='Session',
        call_function='set_keys',
        call_params={
            'keys': session_key,
            # `proof` (Vec<u8>) is the ownership proof from `rotateKeysWithOwner`;
            # verified by runtimes carrying polkadot-sdk#1739, ignored by older ones.
            'proof': proof
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
