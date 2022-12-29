from app.lib.kubernetes_client import get_pod, get_pod_logs


async def get_node_pod_logs(node_name):
    pod = get_pod(node_name)
    return get_pod_logs(pod.metadata.name, pod.metadata.namespace)
