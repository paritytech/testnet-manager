import requests
import logging

from app.config.network_configuration import network_healthy_min_peer_count
from substrateinterface import Keypair

log = logging.getLogger('node_utils')


def get_node_health(node_http_endpoint):
    try:
        return requests.get(node_http_endpoint + '/health', headers={'Content-type': 'application/json'})
    except Exception as err:
        log.error("Failed to call /health on {}; Error: {}".format(node_http_endpoint, err))
        return False


def has_pod_node_role_label(pod):
    return (pod.metadata.labels.get('role') == 'full'
            or pod.metadata.labels.get('role') == 'authority'
            or pod.metadata.labels.get('role') == 'collator')


def is_node_ready(node_http_endpoint):
    try:
        health = get_node_health(node_http_endpoint)
        if health.status_code == 200:
            return check_readiness_from_health(node_http_endpoint, health)
        else:
            log.error("Call {}/health, returned status_code {}".format(node_http_endpoint, health.status_code))
            return False
    except Exception as err:
        log.error("Failed to call get node_readiness on {}; Error: {}".format(node_http_endpoint, err))
        return False


def check_readiness_from_health(node_http_endpoint, health):
    if 'result' in health.json():
        health_status = health.json()['result']
    else:
        health_status = health.json()
    healthy_min_peer_count = network_healthy_min_peer_count()

    status = not health_status['isSyncing'] and health_status['peers'] >= healthy_min_peer_count
    if status:
        log.debug("{} is ready, health: {}, healthy_min_peer_count: {}".format(node_http_endpoint, health_status,
                                                                               healthy_min_peer_count))
    else:
        log.error("{} is NOT ready, health: {}, healthy_min_peer_count: {}".format(node_http_endpoint, health_status,
                                                                                   healthy_min_peer_count))
    return status


# is_node_ready don't check time for last block, node have 0 blocks when parachain not onboarded.
def is_node_ready_ws(node_client):
    try:
        last_block_number = node_client.query('System', 'Number', params=[]).value
        health = node_client.rpc_request(method="system_health", params=[])['result']
        if last_block_number > 0 and not health['isSyncing']:  # todo add check for last block time.
            return True
        else:
            return False
    except Exception as err:
        log.error("Failed to call System.Number on {}; Error: {}".format(getattr(node_client, 'url', 'NO_URL'), err))
        return False

def get_node_version(node_client):
    try:
        return node_client.rpc_request(method='system_version', params=[])['result']
    except Exception as err:
        log.error("Failed to call system_version on {}; Error: {}".format(getattr(node_client, 'url', 'NO_URL'), err))
        return None


# returns {"currentBlock":*,"highestBlock":*,"startingBlock":*}
def get_node_sync_state(node_client):
    try:
        return node_client.rpc_request(method='system_syncState', params=[])['result']
    except Exception as err:
        log.error("Failed to call system_syncState on {}; Error: {}".format(getattr(node_client, 'url', 'NO_URL'), err))
        return None


# returns {'spec_version': 9230, 'spec_name': 'rococo'}
def get_last_runtime_upgrade(node_client):
    try:
        return node_client.query("System", "LastRuntimeUpgrade").value['spec_version']
    except Exception as err:
        log.error("Failed to call System.LastRuntimeUpgrade on {}; Error: {}".format(getattr(node_client, 'url', 'NO_URL'), err))
        return None


def inject_key(node_client, key_uri, key_type='aura'):
    keypair = Keypair.create_from_uri(key_uri)
    key_pub = '0x' + keypair.public_key.hex()
    try:
        node_client.rpc_request(method="author_insertKey", params=[key_type, key_uri, key_pub])
        return key_pub
    except Exception as err:
        log.error("Failed to call author_insertKey on {}; Error: {}".format(getattr(node_client, 'url', 'NO_URL'), err))
        return None
