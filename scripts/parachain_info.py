# Usage python /parachain_info.py wss://parachain-rpc.url [local_directory_name]
import sys

# install with `pip install substrate-interface
from substrateinterface import SubstrateInterface


def get_parachain_head(node_client):
    block_header = node_client.rpc_request(method="chain_getHeader", params=[])
    return convert_header(block_header['result'], node_client)


def convert_header(plain_header, substrate):
    raw_header = '0x'
    raw_header += plain_header['parentHash'].replace('0x', '')
    raw_header += str(substrate.encode_scale('Compact<u32>', int(plain_header['number'], 16))).replace('0x', '')
    raw_header += plain_header['stateRoot'].replace('0x', '')
    raw_header += plain_header['extrinsicsRoot'].replace('0x', '')
    raw_header += str(substrate.encode_scale('Compact<u32>', len(plain_header['digest']['logs']))).replace('0x', '')
    for lg in plain_header['digest']['logs']:
        raw_header += lg.replace('0x', '')
    return raw_header


def get_parachain_wasm(node_client):
    # query for Substrate.Code see: https://github.com/polkascan/py-substrate-interface/issues/190
    block_hash = node_client.get_chain_head()
    parachain_wasm = node_client.get_storage_by_key(block_hash, "0x3a636f6465")
    return parachain_wasm

if len(sys.argv) > 1:
    url = sys.argv[1]
    file_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp'
    node_client = SubstrateInterface(url=url)

    para_id = node_client.query('ParachainInfo', 'ParachainId', params=[]).value
    print(f'Parachain ID={para_id}')

    state = get_parachain_head(node_client)
    with open(f'{file_path}/state-{para_id}', 'a') as file:
        file.write(state)
    print(f'Chain state writen to /tmp/state-{para_id}')

    wasm = get_parachain_wasm(node_client)
    with open(f'{file_path}/wasm-{para_id}', 'a') as file:
        file.write(wasm)
    print(f'Chain wasm writen to /tmp/wasm-{para_id}')
else:
    print('No WS URL passed as arg')
