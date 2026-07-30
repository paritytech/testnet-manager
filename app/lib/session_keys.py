import hashlib
import logging
import requests
from eth_keys.datatypes import PrivateKey as EcdsaPrivateKey
from substrateinterface import Keypair, KeypairType
from app.lib.substrate import get_substrate_client, substrate_call

log = logging.getLogger('session_keys')

# Westend/versi `SessionKeys` in struct order, with each key's crypto scheme:
# grandpa (ed25519), babe/para_validator/para_assignment/authority_discovery
# (sr25519), beefy (ecdsa). The 4-byte key-type ids match the runtime's KeyTypeIds.
_SESSION_KEY_SPECS = [
    ("gran", KeypairType.ED25519),
    ("babe", KeypairType.SR25519),
    ("para", KeypairType.SR25519),
    ("asgn", KeypairType.SR25519),
    ("audi", KeypairType.SR25519),
    ("beef", KeypairType.ECDSA),
]

# `sp_core::proof_of_possession` prefixes the owner with this 4-byte context tag.
_POP_CONTEXT = b"POP_"


def _blake2_256(data):
    return hashlib.blake2b(data, digest_size=32).digest()


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


def _pop_signature(key_type, crypto_type, seed_hex, private_seed, statement):
    """Sign the proof-of-possession statement with one session key.

    sr25519/ed25519 sign the raw statement (matches `sp_io::crypto`); ecdsa signs
    `blake2_256(statement)` in the 65-byte r||s||recid form. NOTE:
    `substrateinterface`'s `Keypair(ECDSA).sign` uses keccak, so we sign the ecdsa
    key with `eth_keys` over the blake2 digest instead.
    """
    if crypto_type == KeypairType.ECDSA:
        return EcdsaPrivateKey(private_seed).sign_msg_hash(_blake2_256(statement)).to_bytes()
    kp = Keypair.create_from_seed(seed_hex, crypto_type=crypto_type)
    return kp.sign(statement)


def generate_and_insert_session_keys(node_http_endpoint, stash_seed):
    """Offline session-key path for nodes whose `generate_session_keys` runtime API
    traps (a stable2512 binary against a post-#1739 runtime, which changed that API
    to v2). Derive the six session keys from deterministic seeds, insert each into
    the node keystore via `author_insertKey` (which does NOT invoke the trapping
    runtime API), and build the ownership proof offline (per-key signatures over the
    `POP_`-tagged stash account id, concatenated in `SessionKeys` order).

    Returns `{'keys': '0x..', 'proof': '0x..'}` or `''` on failure.
    """
    try:
        stash = Keypair.create_from_uri(stash_seed)
        owner = stash.public_key  # SCALE(AccountId32) == the raw 32-byte public key
        statement = _POP_CONTEXT + owner

        keys = b""
        proof = b""
        for key_type, crypto_type in _SESSION_KEY_SPECS:
            # Deterministic per-(validator, key-type) raw seed. Raw seeds sidestep
            # substrateinterface's ecdsa derivation only accepting BIP44 paths, and
            # the node derives the same key from the same `0x`-seed SURI.
            seed = _blake2_256(stash_seed.encode() + key_type.encode())
            seed_hex = "0x" + seed.hex()

            if crypto_type == KeypairType.ECDSA:
                public = EcdsaPrivateKey(seed).public_key.to_compressed_bytes()  # 33 bytes
            else:
                public = Keypair.create_from_seed(seed_hex, crypto_type=crypto_type).public_key

            resp = requests.post(node_http_endpoint, json={
                "id": 1, "jsonrpc": "2.0", "method": "author_insertKey",
                "params": [key_type, seed_hex, "0x" + public.hex()],
            }, headers={'Content-type': 'application/json'}, timeout=10)
            body = resp.json()
            if resp.status_code != 200 or 'error' in body:
                log.error("author_insertKey({}) failed on {}: {}".format(
                    key_type, node_http_endpoint, body.get('error')))
                return ''

            keys += public
            proof += _pop_signature(key_type, crypto_type, seed_hex, seed, statement)

        log.info("{} session keys inserted offline (bypassing generate_session_keys)".format(
            node_http_endpoint))
        return {'keys': "0x" + keys.hex(), 'proof': "0x" + proof.hex()}
    except Exception as err:
        log.error("Offline session-key insertion failed on {}; Error: {}".format(
            node_http_endpoint, err))
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
