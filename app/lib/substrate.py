import logging
from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException
from websocket import WebSocketConnectionClosedException, WebSocketBadStatusException, WebSocketTimeoutException
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
            except (WebSocketConnectionClosedException, ConnectionRefusedError,
                    WebSocketBadStatusException, BrokenPipeError, SubstrateRequestException,
                    WebSocketTimeoutException) as e:
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
            log.error("unable to connect to substrate. url: {}, Error: {}".format(url, e))
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
    extrinsic = substrate_client.create_signed_extrinsic(
        call=call,
        keypair=keypair,
    )

    try:
        receipt = substrate_client.submit_extrinsic(extrinsic, wait_for_inclusion=wait)
        log.info("Extrinsic '{}' sent".format(receipt.extrinsic_hash))
        return receipt
    except Exception as e:
        log.error("Failed to send call: {}, Error: {}".format(call, e))
        return False


def substrate_sudo_call(substrate_client, keypair, payload):
    call = substrate_client.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={
            'call': payload.value,
        }
    )
    return substrate_call(substrate_client, keypair, call)


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
