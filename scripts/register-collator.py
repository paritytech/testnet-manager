#!/usr/bin/env python3
from substrateinterface import SubstrateInterface, Keypair
from app.lib.session_keys import set_node_session_key
from app.lib.balance_utils import transfer_funds
from app.lib.substrate import substrate_call
from substrateinterface.exceptions import SubstrateRequestException

## Step 1: Generating stash account
NODE_NAME = "localrococo-statemint-c-node-0"
PARA_NODE_WS_ENDPOINT = "ws://localhost:9951"
# Alice key
ROOT_SEED = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"
STASH_SEED = ROOT_SEED + "//collator//" + NODE_NAME

node_client = SubstrateInterface(url=PARA_NODE_WS_ENDPOINT)
keypair = Keypair.create_from_uri(STASH_SEED, ss58_format=0)
relay_client = SubstrateInterface(url="ws://localhost:9944")

## Step 2: check enough funds
# export STASH_ADDRESS=$(subkey inspect --output-type Json $STASH_SEED | jq -r .ss58Address)
# export STASH_FUNDS=$(polkadot-js-routers --ws $PARA_WS_ENDPOINT query.system.account $STASH_ADDRESS | jq -r .account.data.free)
print("# Check that stash funds should be more than `collatorSelection.candidacyBond")
relay_sudo = Keypair.create_from_uri(ROOT_SEED+"//Alice")
keypair_rich = Keypair.create_from_uri(ROOT_SEED+"//Alice", ss58_format=0)
account_info = node_client.query('System', 'Account', params=[keypair.ss58_address])
candidacyBond = node_client.query('CollatorSelection', 'CandidacyBond', params=[]).value
if account_info.value['data']['free'] < candidacyBond + 0.1 * 10 ** 10:
    print("Funding {}".format(keypair.ss58_address))
    # candidacyBond +  1 tx fee
    transfer_funds(node_client, keypair_rich, keypair.ss58_address, candidacyBond + 0.1 * 10 ** 10)

# print("# inject key")
# node_client.rpc_request(method="author_insertKey",
#                         params=['aura', STASH_SEED, '0x' + keypair.public_key.hex()])


## Step 3 : Generating and setting session keys
# rotate key on node (require access to unsafe call)
session_key = node_client.rpc_request(method="author_rotateKeys", params=[])['result']
# set session key on parachain
# polkadot-js-routers --ws $PARA_WS_ENDPOINT --seed $STASH_SEED tx.session.setKeys $SESSION_KEY None
print("Set session key:", set_node_session_key(PARA_NODE_WS_ENDPOINT, STASH_SEED, session_key))


## Step 4: Increase the desired candidate count
# polkadot-js-routers --ws $PARA_WS_ENDPOINT query.collatorSelection.desiredCandidates
# check `collatorSelection.desiredCandidates` > ` query.collatorSelection.candidates` + number of collators we want to onboard
# ## Remarks
# Should be greater than the  + the length of the array returned from
# polkadot-js-routers --ws $PARA_WS_ENDPOINT query.collatorSelection.candidates
#
new_desiredCandidates = len(node_client.query('CollatorSelection', 'Candidates').value) + 1
print("Candidates", node_client.query('CollatorSelection', 'Candidates'))
print("Current DesiredCandidates", node_client.query('CollatorSelection', 'DesiredCandidates'))
print("New DesiredCandidates", new_desiredCandidates)
# # Construct parachainSystem.authorizeUpgrade(hash) call on the parachain (e.g. Statemine) and grab the encoded call
call = node_client.compose_call(
    call_module='CollatorSelection',
    call_function='set_desired_candidates',
    call_params={
        'max': new_desiredCandidates
    }
)
encoded_call = call.encode()
print('encoded_call', encoded_call)
# Dispatch XCM call from Relay Chain using
# sudo.sudoUncheckedWeight(palletXcm.sendXcm(Transact(encodedAuthorizeUpgradeCall)))
payload = relay_client.compose_call(
    call_module='XcmPallet',
    call_function='send',
    call_params={
        'dest': {'V0': {'X1': {'Parachain': 1003}}},
            'message': {'V0': {'Transact': ('Superuser', 1000000000, {'encoded': str(encoded_call)})}}
    }
)
call = relay_client.compose_call(
    call_module='Sudo',
    call_function='sudo_unchecked_weight',
    call_params={
        'call': payload.value,
        'weight': 1
    }
)
extrinsic = relay_client.create_signed_extrinsic(
    call=call,
    keypair=relay_sudo
)
try:
    receipt = relay_client.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    print('Relay: Extrinsic "{}" included in block "{}"'.format(receipt.extrinsic_hash, receipt.block_hash))
except SubstrateRequestException as e:
    print("Failed to send: {}".format(e))
    exit(1)

## Step 5: Register as Collator candidate
# polkadot-js-routers --ws $PARA_WS_ENDPOINT --seed $STASH_SEED tx.collatorSelection.registerAsCandidate
call = node_client.compose_call(
    call_module='CollatorSelection',
    call_function='register_as_candidate',
)
receipt = substrate_call(node_client, keypair, call)
print("register_as_candidate", receipt.is_success)
if receipt.is_success:
    print('✅ Success')
else:
    print('⚠️ Extrinsic Failed: ', receipt.error_message)
