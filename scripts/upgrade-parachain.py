#!/usr/bin/env python3
# Usage python ./upgrade-parachain.py wss://relay-chain-rpc.url wss://para-chain-rpc.url 0xrelay_sudo_seed /path/to/runtime
# python ./upgrade-parachain.py  wss://westend-rpc.polkadot.io  wss://westend-bridge-hub-rpc.polkadot.io 0xrelay_sudo_seed.... /home/user/Downloads/...

import sys

import click
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.utils.hasher import blake2_256
from app.lib.parachain_manager import parachain_runtime_upgrade

if len(sys.argv) > 3:
    relay_ws = sys.argv[1]
    parachain_ws = sys.argv[2]
    sudo_key = sys.argv[3]
    runtime_file = sys.argv[4]

    relay_sudo_keypair = Keypair.create_from_seed(sudo_key)
    relay = SubstrateInterface(url=relay_ws)
    parachain = SubstrateInterface(url=parachain_ws)
    para_id = parachain.query('ParachainInfo', 'ParachainId', params=[]).value
    sudo_pub = relay.query('Sudo', 'Key', params=[]).value
    print("Runtime file:", runtime_file)
    print("Parachain id:", para_id)
    if sudo_pub == relay_sudo_keypair.ss58_address:
        print("Sudo key: True")
    else:
        print("Provided wrong sudo key {}, expected {}".format(relay_sudo_keypair.ss58_address, sudo_pub))
        exit(1)

    # Get the Blake-2_256 hash (you may also toggle “hash a file” in the Apps UI and the Blake2_256 code_hash will be
    # computed for you)
    with open(runtime_file, 'rb') as f:
        binarycontent = f.read(-1)
    code_hash = "0x" + blake2_256(binarycontent).hex()
    print("code_hash:", code_hash)


    if click.confirm('Do you want to continue?', default=False):
        parachain_runtime_upgrade("Runtime name", para_id, binarycontent, parachain, relay, relay_sudo_keypair,
                                  check_version=True)

    else:
        print('Do nothing')
        exit(0)

else:
    print('No WS URL passed as arg')
