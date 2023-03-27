import hashlib
import logging
from substrateinterface import SubstrateInterface, Keypair
from app.config.network_configuration import network_ws_endpoint, node_ws_endpoint, network_sudo_seed
from app.config import ws_pool

log = logging.getLogger(__name__)


def get_substrate_client(url):
    log.debug('get_substrate_client: url: {}, network_connection_pool: {}'.format(url,
                                                                                  ws_pool.network_connection_pool))
    if url in ws_pool.network_connection_pool:
        # if it is a websocket connection check it before sending.
        if ws_pool.network_connection_pool[url].websocket:
            try:
                ws_pool.network_connection_pool[url].websocket.ping()
            except Exception as e:
                log.info("Fixing broken WebSocket connection {}, Msg: {}".format(url, e))
                try:
                    ws_pool.network_connection_pool[url].connect_websocket()
                    return ws_pool.network_connection_pool[url]
                except Exception as e:
                    log.error("Failed to connect to websocket, url: {}, Error: {}".format(url, e))
                    # remove connection from pool
                    ws_pool.network_connection_pool.pop(url)
                    return None
        return ws_pool.network_connection_pool[url]
    else:
        try:
            ws_pool.network_connection_pool[url] = SubstrateInterface(url=url)
            return ws_pool.network_connection_pool[url]
        except Exception as e:
            log.error("Unable to connect to substrate. url: {}, Error: {}".format(url, e))
            return None


def get_relay_chain_client():
    url = network_ws_endpoint()
    return get_substrate_client(url)


def get_node_client(node_name):
    return get_substrate_client(node_ws_endpoint(node_name))


def substrate_rpc_request(substrate_client, method, params=[]):
    try:
        return substrate_client.rpc_request(method=method, params=params)['result']
    except Exception as err:
        log.error(f'Failed to call system_health on {getattr(substrate_client, "url", "NO_URL")}; Error: {err}')
        return None


def substrate_call(substrate_client, keypair, call, wait=True):
    if keypair:
        extrinsic = substrate_client.create_signed_extrinsic(
            call=call,
            keypair=keypair,
        )
    else:
        extrinsic = substrate_client.create_unsigned_extrinsic(
            call=call
        )

    try:
        receipt = substrate_client.submit_extrinsic(extrinsic, wait_for_inclusion=wait)
        log.info("Extrinsic '{}' sent".format(receipt.extrinsic_hash))
        return receipt
    except Exception as e:
        log.error("Failed to send call: {}, Error: {}".format(call, e))
        return False


def substrate_sudo_call(substrate_client, keypair, payload, wait=True):
    call = substrate_client.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={
            'call': payload.value,
        }
    )
    return substrate_call(substrate_client, keypair, call, wait)


def substrate_sudo_unchecked_weight_call(substrate_client, keypair, payload, wait=True):
    call = substrate_client.compose_call(
        call_module='Sudo',
        call_function='sudo_unchecked_weight',
        call_params={
            'call': payload.value,
            'weight': {
                'ref_time': 0,
                'proof_size': 0
            }
        }
    )
    return substrate_call(substrate_client, keypair, call, wait)


def substrate_batchall_call(substrate_client, keypair, batch_call, wait=True, sudo=False):
    call = substrate_client.compose_call(
        call_module='Utility',
        call_function='batch',
        call_params={
            'calls': batch_call
        }
    )
    if sudo:
        return substrate_sudo_call(substrate_client, keypair, call, wait)
    else:
        return substrate_call(substrate_client, keypair, call, wait)


# Default weight values
# weight_ref_time: 1*10^12 (1s)
# weight_proof_size: 3145828 (=3*1024*1024)
def substrate_wrap_with_weight(substrate_client, payload, weight_ref_time, weight_proof_size):
    return substrate_client.compose_call(
        call_module='Utility',
        call_function='with_weight',
        call_params={
            'call': payload.value,
            'weight': {
                'ref_time': weight_ref_time,
                'proof_size': weight_proof_size
            }
        }
    )


def substrate_wrap_with_scheduler(substrate_client, payload, schedule_name, schedule_when, schedule_priority):
    schedule_id = f'0x{hashlib.blake2s(schedule_name.encode()).hexdigest()}'
    log.info(f'Wrapping call with named scheduler; id=blake2s("{schedule_name}")={schedule_id}')
    return substrate_client.compose_call(
        call_module='Scheduler',
        call_function='schedule_named',
        call_params={
            'id': schedule_id,
            'when': schedule_when,
            'maybe_periodic': None,
            'priority': schedule_priority,
            'call': payload.value
        }
    )


def substrate_query(substrate_client, module, function, params=[]):
    try:
        return substrate_client.query(module, function, params=params).value
    except Exception as e:
        log.error("Failed to query: {} {}.{}, Error: {}".format(getattr(substrate_client, 'url', 'NO_URL'),
                                                                module, function, e))
        return None


def substrate_query_url(url, module, function,params=[]):
    substrate_client = get_substrate_client(url)
    return substrate_query(substrate_client, module, function, params)


def substrate_sudo_relay_xcm_call(para_id, encoded_message):
    substrate_client = get_relay_chain_client()
    keypair = Keypair.create_from_seed(network_sudo_seed())
    return substrate_xcm_call(substrate_client, keypair, para_id, encoded_message)


def substrate_xcm_call(substrate_client, keypair, para_id, encoded_message):
    payload = substrate_client.compose_call(
        call_module='XcmPallet',
        call_function='send',
        call_params={
            'dest': {'V0': {'X1': {'Parachain': para_id}}},
            'message': {'V0': {'Transact': ('Superuser', 1000000000, {'encoded': str(encoded_message)})}}
        }
    )
    return substrate_sudo_call(substrate_client, keypair, payload)
