# Usage python /export-relaychain-registered-parachains.py wss://relay-chain-rpc.url [local_directory_name]
import sys

# install with `pip install substrate-interface
from substrateinterface import SubstrateInterface


if len(sys.argv) > 1:
    url = sys.argv[1]
    file_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp'
    node_client = SubstrateInterface(url=url)

    para_ids = node_client.query('Paras', 'Parachains', params=[]).value
    print(f'Parachain IDs={para_ids}')
    for para_id in para_ids:
        para_head = node_client.query('Paras', 'Heads', params=[para_id]).value
        para_current_code_hash = node_client.query('Paras', 'CurrentCodeHash', params=[para_id]).value
        para_code = node_client.query('Paras', 'CodeByHash', params=[para_current_code_hash]).value
        with open(f'{file_path}/{para_id}-exported.state', 'a') as file:
            file.write(para_head)
        print(f'Parachain ID={para_id} state writen to /tmp/{para_id}-exported.state')

        with open(f'{file_path}/{para_id}-exported.wasm', 'a') as file:
            file.write(para_code)
        print(f'Parachain ID={para_id} wasm writen to /tmp/{para_id}-exported.wasm')

else:
    print('No WS URL passed as arg')
