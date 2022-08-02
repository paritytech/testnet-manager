# Usage python /onboard-parachain.py wss://relay-chain-rpc.url para_id state_file_path wasm_file_path relay_sudo_seed

import sys

# install with `pip install substrate-interface
from substrateinterface import SubstrateInterface, Keypair

if len(sys.argv) > 1:
    url = sys.argv[1]
    para_id = sys.argv[2]
    para_state_file_path = sys.argv[3]
    para_wasm_file_path = sys.argv[4]
    relay_sudo_keypair = Keypair.create_from_uri(sys.argv[5])
    substrate_client = SubstrateInterface(url=url)

    with open(para_state_file_path, 'r') as para_state_file:
        para_state = para_state_file.readline()
    with open(para_wasm_file_path, 'r') as para_wasm_file:
        para_wasm = para_wasm_file.readline()

    payload = substrate_client.compose_call(
        call_module='ParasSudoWrapper',
        call_function='sudo_schedule_para_initialize',
        call_params={
            'id': para_id,
            'genesis': {
                'genesis_head': para_state,
                'validation_code': para_wasm,
                'parachain': True
            }
        }
    )
    call = substrate_client.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={
            'call': payload.value,
        }
    )
    extrinsic = substrate_client.create_signed_extrinsic(
        call=call,
        keypair=relay_sudo_keypair,
    )

    receipt = substrate_client.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    print("Extrinsic '{}' sent".format(receipt.extrinsic_hash))

else:
    print('No WS URL passed as arg')
