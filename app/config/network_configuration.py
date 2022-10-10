import logging
from os import environ

log = logging.getLogger(__name__)


def get_var_from_env(var):
    value = environ.get(var)
    if value is None:
        log.error("Cannot retrieve value from " + var)
    return value


def get_network():
    return get_var_from_env('NAMESPACE')


def get_namespace():
    return get_var_from_env('NAMESPACE')


def get_node_logs_link():
    node_logs_link = get_var_from_env('NODE_LOGS_LINK')
    if node_logs_link is None:
        return []
    else:
        return node_logs_link


def network_ws_endpoint():
    return get_var_from_env('WS_ENDPOINT')


def node_http_endpoint(node_name):
    node_http_pattern = get_var_from_env('NODE_HTTP_PATTERN')
    return node_http_pattern.replace("NODE_NAME", node_name)


def node_ws_endpoint(node_name):
    node_ws_pattern = get_var_from_env('NODE_WS_PATTERN')
    return node_ws_pattern.replace("NODE_NAME", node_name)


def network_validators_root_seed():
    return get_var_from_env('VALIDATORS_ROOT_SEED')

def network_sudo_seed():
    return get_var_from_env('SUDO_SEED')


def network_healthy_min_peer_count():
    return int(get_var_from_env('HEALTHY_MIN_PEER_COUNT'))


def network_tasks_cron_schedule():
    return get_var_from_env('TASKS_CRON_SCHEDULE')


def network_consensus():
    # poa or pos (default id poa )
    value = get_var_from_env('TESTNET_MANAGER_CONSENSUS')
    if value is None:
        value = "poa"
    return value.lower()
