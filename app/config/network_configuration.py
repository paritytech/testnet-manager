import logging
from os import environ

log = logging.getLogger(__name__)


def get_var_from_env(var):
    value = environ.get(var)
    if value is None:
        log.warning("Cannot retrieve value from " + var)
    return value


def get_network():
    return get_var_from_env('NAMESPACE')


def get_namespace():
    return get_var_from_env('NAMESPACE')


def get_node_logs_link():
    node_logs_link = get_var_from_env('NODE_LOGS_LINK')
    if node_logs_link is None:
        # If unset set, use the link to the internal node logs endpoint
        return '/api/nodes/{node}/logs'
    else:
        return node_logs_link


def get_relay_chain_rpc_url():
    if environ.get('WS_ENDPOINT'):
        log.warning('WS_ENDPOINT will be deprecated. Please update to RELAY_CHAIN_RPC_URL.')
        return get_var_from_env('WS_ENDPOINT')
    else:
        return get_var_from_env('RELAY_CHAIN_RPC_URL')


# Retain HTTP endpoint until HTTP RPC is completely removed
def node_http_endpoint(node_name):
    if environ.get('NODE_HTTP_PATTERN'):
        log.warning('NODE_HTTP_PATTERN will be deprecated. Please update to RPC_NODE_URL_PATTERN.')
        node_http_pattern = get_var_from_env('NODE_HTTP_PATTERN')
        return node_http_pattern.replace("NODE_NAME", node_name)
    else:
        node_http_pattern = get_var_from_env('RPC_NODE_URL_PATTERN')
        return f'ws://{node_http_pattern.replace("NODE_NAME", node_name)}'

# Retain WS endpoint until HTTP RPC is completely removed
def node_ws_endpoint(node_name):
    if environ.get('NODE_WS_PATTERN'):
        log.warning('NODE_WS_PATTERN will be deprecated. Please update to RPC_NODE_URL_PATTERN.')
        node_ws_pattern = get_var_from_env('NODE_WS_PATTERN')
        return node_ws_pattern.replace("NODE_NAME", node_name)
    else:
        node_ws_pattern = get_var_from_env('RPC_NODE_URL_PATTERN')
        return f'ws://{node_ws_pattern.replace("NODE_NAME", node_name)}'


def derivation_root_seed():
    return get_var_from_env('DERIVATION_ROOT_SEED')


def network_sudo_seed():
    return get_var_from_env('SUDO_SEED')


def get_relay_chain_ss58_format():
    relay_chain_ss58_format = get_var_from_env('RELAY_CHAIN_SS58_FORMAT')
    if relay_chain_ss58_format is None:
        # If unset set, set to Rococo value
        return '42'
    else:
        return relay_chain_ss58_format


def network_healthy_min_peer_count():
    return int(get_var_from_env('HEALTHY_MIN_PEER_COUNT'))


def network_tasks_cron_schedule():
    return get_var_from_env('TASKS_CRON_SCHEDULE')


def relay_chain_consensus():
    # poa or pos (default id poa )
    value = get_var_from_env('RELAY_CHAIN_CONSENSUS')
    if value is None:
        value = "poa"
    return value.lower()


def network_external_validators_configmap():
    external_validators_configmap = get_var_from_env('EXTERNAL_VALIDATORS_CONFIGMAP')
    if external_validators_configmap is None:
        return "external-validators"
    return external_validators_configmap
