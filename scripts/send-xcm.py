#!/usr/bin/env python3
# Usage python ./send-xcm.py wss://relay-chain-rpc.url wss://parar-chain-rpc.url  0xrelay_sudo_seed  0xcall

import sys
from datetime import datetime

import click
import time

from scalecodec import ScaleBytes
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.hasher import blake2_256
from app.lib.substrate import substrate_xcm_sudo_transact_call, get_query_weight


if len(sys.argv) > 3:
    relay_ws = sys.argv[1]
    parar_ws = sys.argv[2]
    sudo_key = sys.argv[3]
    xcm = sys.argv[4]

    relay_sudo_keypair = Keypair.create_from_seed(sudo_key)
    relay = SubstrateInterface(url=relay_ws)
    para = SubstrateInterface(url=parar_ws)

    sudo_pub = relay.query('Sudo', 'Key', params=[]).value
    para_id = para.query('ParachainInfo', 'ParachainId', params=[]).value
    call_obj = para.create_scale_object("Call")
    call_obj.decode(ScaleBytes(xcm))
    weight = get_query_weight(para, call_obj)
    if sudo_pub == relay_sudo_keypair.ss58_address:
        print("Sudo key: True")
    else:
        print("Provided wrong sudo key {}, expected {}".format(relay_sudo_keypair.ss58_address, sudo_pub))
        exit(1)

    print("relay_ws:", relay_ws)
    print("para_ws:", parar_ws)
    print("para_id:", para_id)
    print("weight:", weight)

    if click.confirm('Do you want to continue?', default=False):
        print('Do sudo.sudoUncheckedWeight(palletXcm.sendXcm(Transact(encodedAuthorizeUpgradeCall)))...')
        try:
            receipt = substrate_xcm_sudo_transact_call(relay, relay_sudo_keypair, para_id, xcm, weight)
            print('Relay: Extrinsic "{}" included in block "{}"'.format(receipt.extrinsic_hash, receipt.block_hash))
            print('https://polkadot.js.org/apps/?rpc={}#/explorer/query/{}'.format(relay_ws, receipt.block_hash))
        except SubstrateRequestException as e:
            print("Failed to send: {}".format(e))
            exit(1)
    else:
        print('Do nothing')
        exit(0)

else:
    print('No WS URL passed as arg')
