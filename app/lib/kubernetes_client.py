from kubernetes import client as kubernetes_client

from app.config.network_configuration import get_namespace

namespace = get_namespace()


def list_stateful_sets():
    return kubernetes_client.CustomObjectsApi().list_namespaced_custom_object(group="apps", version="v1", plural="statefulsets", namespace=namespace)['items']


def list_validator_stateful_sets(role='authority'):
    stateful_sets = list_stateful_sets()
    validator_stateful_sets = list(filter(lambda sts: sts['spec']['template']['metadata']['labels']['role'] == role, stateful_sets))
    return list(map(lambda sts: sts['metadata']['name'], validator_stateful_sets))


def list_parachain_collator_stateful_sets(para_id):
    stateful_sets = kubernetes_client.CustomObjectsApi().list_namespaced_custom_object(group="apps", version="v1", plural="statefulsets", namespace=namespace)
    collator_stateful_sets = list(filter(lambda sts: sts['spec']['template']['metadata']['labels']['role'] == 'collator' and
                                                     sts['spec']['template']['metadata']['labels']['paraId'] == para_id,
                                         stateful_sets['items']))
    return list(map(lambda sts: sts['metadata']['name'], collator_stateful_sets))


def get_pod(pod_name):
    pod = kubernetes_client.CoreV1Api().read_namespaced_pod(namespace=namespace, name=pod_name)
    return pod


def list_substrate_node_pods(role_label=''):
    pods = kubernetes_client.CoreV1Api().list_namespaced_pod(namespace=namespace).items
    # Keep only pods which are substrate nodes
    pods = list(filter(lambda pod: pod.metadata.labels.get('app.kubernetes.io/name') == "node", pods))
    if role_label:
        return list(filter(lambda pod: pod.metadata.labels.get('role') == role_label, pods))
    else:
        return pods


def list_validator_pods(stateful_set_name):
    validator_pods = list_substrate_node_pods('authority')
    if stateful_set_name:
        validator_pods = list(filter(lambda pod: pod.metadata.owner_references[0].name == stateful_set_name, validator_pods))
    return validator_pods


def list_collator_pods(para_id=None, stateful_set_name=None):
    collator_pods = list_substrate_node_pods('collator')
    if stateful_set_name:
        collator_pods = list(filter(lambda pod: pod.metadata.owner_references[0].name == stateful_set_name, collator_pods))
    if para_id:
        collator_pods = list(filter(lambda pod: pod.metadata.labels.get('paraId') == para_id, collator_pods))
    return collator_pods


def get_external_validators_from_configmap():
    try:
        external_validator_configmap = kubernetes_client.CoreV1Api().read_namespaced_config_map(name='external-validators', namespace=get_namespace())
        return external_validator_configmap.data if external_validator_configmap.data is not None else {}
    except Exception:
        return {}


def get_pod_logs(name, namespace):
    return kubernetes_client.CoreV1Api().read_namespaced_pod_log(name=name, namespace=namespace)
