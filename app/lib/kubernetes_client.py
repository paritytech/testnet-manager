from kubernetes import client as kubernetes_client

from app.config.network_configuration import get_namespace, network_external_validators_configmap

namespace = get_namespace()


def get_pod(pod_name):
    pod = kubernetes_client.CoreV1Api().read_namespaced_pod(namespace=namespace, name=pod_name)
    return pod


def get_pod_details(pod_name):
    pod = get_pod(pod_name)
    volume_details = []

    # Get the specs of each volume
    for volume in pod.spec.volumes:
        if volume.persistent_volume_claim:
            pvc_name = volume.persistent_volume_claim.claim_name
            volume_specs = get_pod_pvc_details(namespace, pvc_name)
            volume_details.append({
                'pvc_name': pvc_name,
                'size': volume_specs['size'],
                'class': volume_specs['class'],
                'phase': volume_specs['phase']
            })


    affinity = pod.spec.affinity
    if affinity:
        affinity_details = get_affinity_details(affinity)
    else:
        affinity_details = {}

    # Get the node name where the pod is scheduled
    pod_node_location = pod.spec.node_name
    node_details = get_pod_node_details(pod_node_location)

    potential_ready = pod.status.phase == "Running"
    container_resources = pod.spec.containers[0].resources

    pod_details = {
        'affinity': affinity_details,
        'limit_cpu': container_resources.limits.get('cpu', '') if container_resources.limits else 'None',
        'limit_memory': container_resources.limits.get('memory', '') if container_resources.limits else 'None',
        'name': pod.metadata.name,
        'namespace': pod.metadata.namespace,
        'node_details': node_details,
        'node_name': pod.spec.node_name,
        'node_selector': pod.spec.node_selector or {},
        'potential_ready': potential_ready,
        'request_cpu': container_resources.requests.get('cpu', '') if container_resources.requests else 'None',
        'request_memory': container_resources.requests.get('memory', '') if container_resources.requests else 'None',
        'restart_count': pod.status.container_statuses[0].restart_count,
        'tolerations': pod.spec.tolerations or [],
        'volume_details': volume_details
    }
    return pod_details


def get_pod_pvc_details(namespace, pvc_name):
    pvc = kubernetes_client.CoreV1Api().read_namespaced_persistent_volume_claim(namespace=namespace, name=pvc_name)
    pvc_details = {
        'size': pvc.spec.resources.requests['storage'],
        'class': pvc.spec.storage_class_name,
        'phase': pvc.status.phase
    }
    return pvc_details


def get_pod_node_details(pod_name):
    node = kubernetes_client.CoreV1Api().read_node(name=pod_name)
    node_details = {}

    for label in ["kubernetes.io/arch", "node.kubernetes.io/instance-type", "kubernetes.io/os"]:
        if label in node.metadata.labels:
            node_details[label] = node.metadata.labels[label]

    if node.status.node_info.kernel_version:
        node_details['kernel-version'] = node.status.node_info.kernel_version
        
    return node_details


def get_affinity_details(affinity):
    affinity_types = [("node_affinity", affinity.node_affinity),
                      ("pod_affinity", affinity.pod_affinity),
                      ("pod_anti_affinity", affinity.pod_anti_affinity)]
    affinity_details = {}

    for affinity_type, affinity_obj in affinity_types:
        if affinity_obj:
            required_during_scheduling = affinity_obj.required_during_scheduling_ignored_during_execution
            if required_during_scheduling:
                affinity_details[affinity_type] = {
                    "policy": "required_during_scheduling",
                    "details": required_during_scheduling
                }

            preferred_during_scheduling = affinity_obj.preferred_during_scheduling_ignored_during_execution
            if preferred_during_scheduling:
                affinity_details[affinity_type] = {
                    "policy": "preferred_during_scheduling",
                    "details": preferred_during_scheduling
                }
    return affinity_details


def list_stateful_sets():
    return kubernetes_client.CustomObjectsApi().list_namespaced_custom_object(group="apps", version="v1",
                                                                              plural="statefulsets",
                                                                              namespace=namespace)['items']


def list_validator_stateful_sets(role='authority'):
    stateful_sets = list_stateful_sets()
    validator_stateful_sets = list(
        filter(lambda sts: sts['spec']['template']['metadata']['labels'].get('role') == role, stateful_sets))
    return list(map(lambda sts: sts['metadata']['name'], validator_stateful_sets))


def list_parachain_collator_stateful_sets(para_id: str):
    stateful_sets = kubernetes_client.CustomObjectsApi().list_namespaced_custom_object(group="apps", version="v1", plural="statefulsets", namespace=namespace)

    collator_stateful_sets = list(
        filter(lambda sts: sts['spec']['template']['metadata']['labels'].get('role') == 'collator' and
                           sts['spec']['template']['metadata']['labels'].get('paraId') == para_id,
               stateful_sets['items']))
    return list(map(lambda sts: sts['metadata']['name'], collator_stateful_sets))


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


def list_collator_pods(para_id: str = None, stateful_set_name: str = None):
    collator_pods = list_substrate_node_pods('collator')
    if stateful_set_name:
        collator_pods = list(filter(lambda pod: pod.metadata.owner_references[0].name == stateful_set_name, collator_pods))
    if para_id:
        collator_pods = list(filter(lambda pod: pod.metadata.labels.get('paraId') == para_id, collator_pods))
    return collator_pods


def get_external_validators_from_configmap():
    try:
        external_validators = kubernetes_client.CoreV1Api().read_namespaced_config_map(
            name=network_external_validators_configmap(),
            namespace=get_namespace()
        )
        return external_validators.data if external_validators.data is not None else {}
    except Exception:
        return {}


def get_pod_logs(name, namespace):
    return kubernetes_client.CoreV1Api().read_namespaced_pod_log(name=name, namespace=namespace)
