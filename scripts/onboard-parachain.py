# Usage python ./onboard-parachain.py wss://relay-chain-rpc.url wss://para-chain-rpc.url 0xrelay_sudo_seed
# python ./onboard-parachain.py  wss://westend-rpc.polkadot.io  wss://westend-bridge-hub-rpc.polkadot.io 0x1111....

import sys

import click
# install with `pip install substrate-interface
from substrateinterface import SubstrateInterface, Keypair
from app.lib.parachain_manager import initialize_parachain, get_chain_wasm, get_parachain_head, \
    get_permanent_slot_lease_period_length


if len(sys.argv) > 2:
    relay_url = sys.argv[1]
    para_url = sys.argv[2]
    sudo_seed = sys.argv[3]
    relay_chain_client = SubstrateInterface(url=relay_url)
    para_chain_client = SubstrateInterface(url=para_url)

    key_from_chain = relay_chain_client.query('Sudo', 'Key', params=[]).value
    key_from_cli = Keypair.create_from_seed(sudo_seed).ss58_address
    if key_from_chain == key_from_cli:
        print("Sudo key: True")
    else:
        print("Provided wrong sudo key {}, expected {}".format(key_from_cli, key_from_chain))
        exit(1)

    para_id = para_chain_client.query('ParachainInfo', 'ParachainId', params=[]).value
    state = get_parachain_head(para_chain_client)
    wasm = get_chain_wasm(para_chain_client)
    permanent_slot_lease_period_length = get_permanent_slot_lease_period_length(relay_chain_client)

    print('Scheduling parachain #{}, state:{}, wasm: {}...{}, lease: {}'.format(
        para_id, state, wasm[0:64], wasm[-64:], permanent_slot_lease_period_length))

    if click.confirm('Do you want to continue?', default=True):
        print('Started...')
        print(initialize_parachain(relay_chain_client, sudo_seed, para_id, state, wasm, permanent_slot_lease_period_length))
        print('Done, check here: https://polkadot.js.org/apps/?rpc={}#/parachains/parathreads '.format(relay_url))
    else:
        print('Do nothing')
else:
    print('No WS URL passed as arg')

