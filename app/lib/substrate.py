import hashlib
import logging
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.utils.hasher import blake2_256

from app.config.network_configuration import get_relay_chain_rpc_url, node_ws_endpoint, network_sudo_seed
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
    url = get_relay_chain_rpc_url()
    return get_substrate_client(url)


# Returns {'ss58Format': int, 'tokenDecimals': int, 'tokenSymbol': str}
def get_chain_properties(substrate_client):
    return substrate_rpc_request(substrate_client, 'system_properties')


def get_node_client(node_name):
    return get_substrate_client(node_ws_endpoint(node_name))


def get_query_weight(substrate_client, call):
    return get_query_info(substrate_client, call)['weight']


# Returns: {'weight': {'ref_time': 178260000, 'proof_size': 3593}, 'class': 'Normal', 'partialFee': 469298416}
def get_query_info(substrate_client, call):
    try:
        keypair = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
        extrinsic = substrate_client.create_signed_extrinsic(call=call, keypair=keypair)
        extrinsic_len = substrate_client.create_scale_object('u32')
        extrinsic_len.encode(len(extrinsic.data))
        return substrate_client.runtime_call("TransactionPaymentApi", "query_info", [extrinsic, extrinsic_len]).value
    except Exception as err:
        log.error(f'Failed to get query_info on {getattr(substrate_client, "url", "NO_URL")}; Error: {err}')
        # TransactionPaymentApi may not be in all parachains, return value which will work in most cases.
        return {'weight': {'ref_time': 1000000000, 'proof_size': 4096}, 'class': 'Normal', 'partialFee': 1000000000}


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


def substrate_proxy_call(substrate_client, keypair, run_as, payload, wait=True):
    call = substrate_client.compose_call(
        call_module='Proxy',
        call_function='proxy',
        call_params={
            'real': run_as,
            'call': payload.value,
            'force_proxy_type': None
        }
    )
    return substrate_call(substrate_client, keypair, call, wait)


def get_sudo_keys(substrate_client):
    sudo = substrate_client.query('Sudo', 'Key', params=[]).value
    proxies = []
    try:
        # proxy_result has two element list of proxies and deposit.
        proxy_result = substrate_client.query('Proxy', 'Proxies', params=[sudo]).value
        for proxy in proxy_result[0]:
            proxies.append(proxy['delegate'])
    except Exception as e:
        print("ERROR: unable to get proxies, error:", e)
    return {'sudo': sudo, 'proxies': proxies}


def substrate_check_sudo_key_and_call(substrate_client, keypair, payload, wait=True):
    sudo_keys = get_sudo_keys(substrate_client)
    provided_key = keypair.ss58_address
    if provided_key == sudo_keys['sudo']:
        return substrate_call(substrate_client, keypair, payload, wait)
    elif provided_key in sudo_keys['proxies']:
        return substrate_proxy_call(substrate_client, keypair, sudo_keys['sudo'], payload, wait)
    else:
        log.error(f"Failed to execute sudo call: {getattr(substrate_client, 'url', 'NO_URL')} {payload.value['call_module']}.{payload.value['call_function']}, Error: Provided wrong sudo key {provided_key}, expected {sudo_keys}")
        return None

def substrate_sudo_call(substrate_client, keypair, payload, wait=True):
    call = substrate_client.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={
            'call': payload.value,
        }
    )
    return substrate_check_sudo_key_and_call(substrate_client, keypair, call, wait)


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
    return substrate_check_sudo_key_and_call(substrate_client, keypair, call, wait)


def substrate_batchall_call(substrate_client, keypair, batch_call, wait=True, sudo=False):
    # If the batch contains only 1 element, don't use batch
    if len(batch_call) == 1:
        call = batch_call[0]
    else:
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


def substrate_wrap_with_weight(substrate_client, payload):
    weight = get_query_weight(substrate_client, payload)
    return substrate_client.compose_call(
        call_module='Utility',
        call_function='with_weight',
        call_params={
            'call': payload.value,
            'weight': weight
        }
    )


def substrate_wrap_with_scheduler(substrate_client, payload, schedule_name, schedule_when, schedule_priority):
    schedule_id = f'0x{blake2_256(schedule_name.encode()).hexdigest()}'
    log.info(f'Wrapping call with named scheduler; id=blake2_256("{schedule_name}")={schedule_id}')
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


def substrate_sudo_relay_xcm_call(para_id, encoded_message, weight):
    substrate_client = get_relay_chain_client()
    keypair = Keypair.create_from_seed(network_sudo_seed())
    return substrate_xcm_sudo_transact_call(substrate_client, keypair, para_id, encoded_message, weight)


def substrate_xcm_sudo_transact_call(substrate_client, keypair, para_id, encoded_message, weight):
    payload = substrate_client.compose_call(
        call_module='XcmPallet',
        call_function='send',
        call_params={
            'dest': {
                'V3': {
                    "parents": 0,
                    'interior': {
                        'X1': {
                            'Parachain': para_id
                        }
                    }
                }
            },
            'message': {
                'V3': [[
                    {
                        'UnpaidExecution': {
                            'weight_limit': 'Unlimited',
                            'check_origin': None
                        }
                    },
                    {
                        'Transact': {
                            'origin_kind': 'Superuser',
                            'require_weight_at_most': weight,
                            'call': {
                                'encoded': str(encoded_message)
                            }
                        }
                    }
                ]]
            }
        })
    return substrate_sudo_call(substrate_client, keypair, payload)
