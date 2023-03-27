from scalecodec.exceptions import RemainingScaleBytesNotEmptyException
from substrateinterface import Keypair
from substrateinterface.utils.hasher import blake2_256

from app.config.network_configuration import network_sudo_seed
from app.lib.network_utils import log
from app.lib.parachain_manager import get_chain_wasm, get_parachain_head, get_parachain_node_client
from app.lib.substrate import get_relay_chain_client, substrate_sudo_call, substrate_wrap_with_weight


def get_substrate_runtime(node_client):
    last_runtime_upgrade = node_client.query("System", "LastRuntimeUpgrade").value
    wasm = get_chain_wasm(node_client)
    code_hash = f'0x{blake2_256(bytearray.fromhex(wasm[2:])).hex()}'
    head = get_parachain_head(node_client)

    return {
        'spec_version': last_runtime_upgrade['spec_version'],
        'spec_name': last_runtime_upgrade['spec_name'],
        'code_hash': code_hash,
        'head': head
    }


def get_relay_runtime():
    node_client = get_relay_chain_client()
    return get_substrate_runtime(node_client)


def get_relay_active_configuration():
    relay_client = get_relay_chain_client()
    try:
        active_config = relay_client.query('Configuration', 'ActiveConfig')
        return active_config.value
    # Catch scale encoding exception happening on Versi
    except RemainingScaleBytesNotEmptyException as err:
        log.error(f'Scale decoding exception: {err}')
        return {}


def update_relay_configuration(new_configuration_key, new_configuration_value):
    relay_client = get_relay_chain_client()
    keypair = Keypair.create_from_seed(network_sudo_seed())
    # See https://polkascan.github.io/py-substrate-metadata-docs/polkadot/configuration/#set_X
    call = relay_client.compose_call('Configuration', f'set_{new_configuration_key}', {'new': new_configuration_value})
    receipt = substrate_sudo_call(relay_client, keypair, call)
    if receipt and receipt.is_success:
        txt = f'Successfully sent Configuration.set_{new_configuration_key}={new_configuration_value} on Relaychain'
        log.info(txt)
        return True, txt
    else:
        err = f"Unable to apply Configuration.set_{new_configuration_key}={new_configuration_value} on Relaychain. " \
              f"Error: {getattr(receipt, 'error_message', None)}"
        log.error(err)
        return False, err


def get_parachain_runtime(para_id):
    para_client = get_parachain_node_client(para_id)
    relay_client = get_relay_chain_client()
    runtime_info = get_substrate_runtime(para_client)
    runtime_info['isParachain'] = True
    runtime_info['parachain_head_in_relay'] = relay_client.query('Paras', 'Heads', params=[para_id]).value
    runtime_info['parachain_code_hash_in_relay'] = relay_client.query('Paras', 'CurrentCodeHash', params=[para_id]).value
    return runtime_info


def runtime_upgrade(runtime, schedule_blocks_wait=None):
    relay_client = get_relay_chain_client()
    code = '0x' + runtime.hex()
    keypair = Keypair.create_from_seed(network_sudo_seed())
    inner_call = relay_client.compose_call(
        call_module='System',
        call_function='set_code',
        call_params={
            'code': code
        }
    )
    # Wrap with weight set to:
    # ref_time: 1*10^12 (1s)
    # proof_size: 3145828 (=3*1024*1024)
    wrapped_call = substrate_wrap_with_weight(relay_client, inner_call, weight_ref_time=1000000000000, weight_proof_size=3145828)
    receipt = substrate_sudo_call(relay_client, keypair, wrapped_call)
    if receipt and receipt.is_success:
        txt = "Successfully sent System.set_code on Relaychain, " \
              "Check results here: https://polkadot.js.org/apps/#/explorer/query/{}".format(receipt.block_hash)
        log.info(txt)
        return True, txt
    else:
        err = "Unable to sent System.set_code. Error: {}".format(
            getattr(receipt, 'error_message', None))
        log.error(err)
        return False, err
