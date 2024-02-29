# Get an extrinsic call in python's substrate-interface format
# usage:
#   poetry run python scripts/get-extrinsic-call.py wss://rococo-rpc.polkadot.io 0x4b495cc8aece8dd54b401bbbc504c960312d3a8da3541e86ef2a617d6e76cc3f 0xabe991d8d0384056cadabeec8827b012b8330114fa0d5489dc6af10bcb105834
import json
import sys
from json import JSONDecodeError

from substrateinterface import SubstrateInterface

rpc_endpoint = sys.argv[1]
block_hash = sys.argv[2]
extrinsic_hash = sys.argv[3]

substrate = SubstrateInterface(url=rpc_endpoint)
receipt = substrate.retrieve_extrinsic_by_hash(block_hash, extrinsic_hash)
# Hack for pretty printing
try:
    print(json.dumps(json.loads(str(receipt.extrinsic['call']).replace("'", "\"").replace('None', 'null')), indent=4).replace("\"", "'"))
except JSONDecodeError:
    print(receipt.extrinsic['call'])