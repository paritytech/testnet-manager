#!/usr/bin/env python3
import time
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.hasher import blake2_256

relay_ws = "wss://westend-rpc.polkadot.io"
parachain_ws = "wss://westmint-rpc.polkadot.io"
runtime_file = "/home/pierre/Downloads/westmint_runtime.compact.compressed.wasm"
sudo_key = ''

relay_sudo_keypair = Keypair.create_from_uri(sudo_key)
relay = SubstrateInterface(url=relay_ws)
parachain = SubstrateInterface(url=parachain_ws)

# Get the Blake-2_256 hash (you may also toggle “hash a file” in the Apps UI and the Blake2_256 code_hash will be
# computed for you)
with open(runtime_file, 'rb') as f:
    binarycontent = f.read(-1)
code_hash = "0x" + blake2_256(binarycontent)
print("code_hash", code_hash)


# Construct parachainSystem.authorizeUpgrade(hash) call on the parachain (e.g. Statemine) and grab the encoded call
call = parachain.compose_call(
    call_module='ParachainSystem',
    call_function='authorize_upgrade',
    call_params={
        'code_hash': code_hash
    }
)
encoded_call = call.encode()
print('encoded_call', encoded_call)

# Dispatch XCM call from Relay Chain using
# sudo.sudoUncheckedWeight(palletXcm.sendXcm(Transact(encodedAuthorizeUpgradeCall)))
payload = relay.compose_call(
    call_module='XcmPallet',
    call_function='send',
    call_params={
        'dest': {'V1': {'parent': 0, 'X1': {'Parachain': 1000}}},
        'message': {'V2': {'Transact': ('Superuser', 1000000000, {'encoded': str(encoded_call)})}}
    }
)
call = relay.compose_call(
    call_module='Sudo',
    call_function='sudo_unchecked_weight',
    call_params={
        'call': payload.value,
        'weight': 1
    }
)

extrinsic = relay.create_signed_extrinsic(
    call=call,
    keypair=relay_sudo_keypair
)

try:
    receipt = relay.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    print('Relay: Extrinsic "{}" included in block "{}"'.format(receipt.extrinsic_hash, receipt.block_hash))
except SubstrateRequestException as e:
    print("Failed to send: {}".format(e))
    exit(1)

# wait or we will get: "1010: Invalid Transaction: Transaction call is not expected"
time.sleep(60)

# After dispatch, submit the compact.compressed.wasm file using the unsigned transaction
# parachainSystem.enactAuthorizedUpgrade. Anyone can submit this extrinsic.
call2 = parachain.compose_call(
    call_module='ParachainSystem',
    call_function='enact_authorized_upgrade',
    call_params={
        'code': '0x'+binarycontent.hex()
    }
)

extrinsic2 = parachain.create_unsigned_extrinsic(
    call=call2
)

try:
    receipt = parachain.submit_extrinsic(extrinsic2)
    print('Parachain: Extrinsic "{}" included in block "{}"'.format(receipt.extrinsic_hash, receipt.block_hash))
except SubstrateRequestException as e:
    print("Failed to send: {}".format(e))
    exit(1)
