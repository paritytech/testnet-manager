from fastapi import APIRouter, Path, Query, Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.config.network_configuration import get_node_logs_link, get_network
from app.lib.kubernetes_client import list_validator_stateful_sets, list_parachain_collator_stateful_sets
from app.lib.network_utils import list_substrate_nodes, list_validators, get_session_queued_keys, list_parachains, \
    list_parachain_collators, get_substrate_node
from app.lib.runtime_utils import get_relay_runtime, get_relay_active_configuration, get_parachain_runtime
from app.lib.parachain_manager import get_all_parachain_lifecycles
from app.lib.substrate import get_relay_chain_client

router = APIRouter()
templates = Jinja2Templates(directory='app/templates')
network = get_network()

@router.get("/",  response_class=HTMLResponse, include_in_schema=False)
async def homepage(request: Request):
    return templates.TemplateResponse('index.html', {'request': request, 'network': network})


@router.get("/nodes", response_class=HTMLResponse, include_in_schema=False)
async def nodes(
    request: Request,
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    nodes = list_substrate_nodes(statefulset)
    return templates.TemplateResponse('nodes.html', dict(request=request,
                                                    network_name=network,
                                                    node_logs_link=get_node_logs_link(),
                                                    nodes=nodes,
                                                    nodes_count=len(nodes),
                                                    validator_count=len(list(filter(lambda node: node['role'] == 'authority', nodes))),
                                                    collator_count=len(list(filter(lambda node: node['role'] == 'collator', nodes))),
                                                    full_nodes_count= len(list(filter(lambda node: node['role'] == 'full', nodes)))))


@router.get("/nodes/{node_name}", response_class=HTMLResponse, include_in_schema=False)
async def get_nodes(
    request: Request,
    node_name: str = Path(description="Name of the node")
):
    return templates.TemplateResponse('node_info.html', dict(request=request, network=network, node=get_substrate_node(node_name)))


@router.get("/validators", response_class=HTMLResponse, include_in_schema=False)
async def validators(
    request: Request,
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    validators = list_validators(statefulset)
    validator_stateful_sets = list_validator_stateful_sets()
    external_validator_count = len(
        list(filter(lambda val: val['is_validator'] and val['location'] == 'external', validators)))
    active_validator_count = len(
        list(filter(lambda val: val['is_validator'] and val['location'] == 'in_cluster', validators)))
    inactive_validator_count = len(
        list(filter(lambda val: not val['is_validator'] and val['location'] == 'in_cluster', validators)))
    deleted_validator_count = len(
        list(filter(lambda val: val['is_validator'] and val['location'] == 'deleted_from_cluster', validators)))
    deleted_validators = list(filter(lambda val: val['is_validator'] and val['location'] == 'deleted_from_cluster', validators))
    deleted_validator_addresses = list(map(lambda val: val['address'], deleted_validators))

    session_keys = get_session_queued_keys()
    for index in range(len(validators)):
        validators[index]['keys'] = session_keys.get(validators[index]['address'], {})

    return templates.TemplateResponse('validators.html', {'request': request,
                                                          'network_name': network,
                                                          'node_logs_link': get_node_logs_link(),
                                                          'validators': validators,
                                                          'external_validator_count': external_validator_count,
                                                          'active_validator_count': active_validator_count,
                                                          'inactive_validator_count': inactive_validator_count,
                                                          'deleted_validator_count': deleted_validator_count,
                                                          'selected_stateful_set': statefulset,
                                                          'validator_stateful_sets': validator_stateful_sets,
                                                          'deleted_validator_addresses': deleted_validator_addresses
                                                          })


@router.get("/parachains", response_class=HTMLResponse, include_in_schema=False)
async def parachains(
    request: Request
):
    parachains = list_parachains()
    paras_count = len(parachains)
    parachain_count = len(list(filter(lambda para: para[1].get('lifecycle') == 'Parachain', parachains.items())))
    parathread_count = len(list(filter(lambda para: 'Parathread' in para[1].get('lifecycle', ''), parachains.items())))

    return templates.TemplateResponse('parachains.html', dict(request=request, network_name=network, parachains=parachains,
                                                         paras_count=paras_count, parachain_count=parachain_count,
                                                         parathread_count=parathread_count))


@router.get("/collators/{para_id}", response_class=HTMLResponse, include_in_schema=False)
async def collators(
    request: Request,
    para_id: str = Path(description="ID of the parachainsfor which to get list of collators"),
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    collators = list_parachain_collators(para_id, statefulset)
    runtime = collators[0]['runtime'] if len(collators) > 0 else ''
    desired_candidates = collators[0]['desired_candidates'] if len(collators) > 0 else ''
    parachain_name = collators[0]['chain'] if len(collators) > 0 else ''

    parachain_lifecycles = get_all_parachain_lifecycles(get_relay_chain_client())
    parachain_status = parachain_lifecycles.get(int(para_id))

    cluster_collator_stateful_set = list_parachain_collator_stateful_sets(para_id)
    external_collator_count = len(
        list(filter(lambda val: val['status'] and val['location'] == 'external', collators)))
    active_collator_count = len(
        list(filter(lambda val: val['status'] and val['location'] == 'in_cluster', collators)))
    inactive_collator_count = len(
        list(filter(lambda val: not val['status'] and val['location'] == 'in_cluster', collators)))
    deleted_collator_count = len(
        list(filter(lambda val: val['status'] and val['location'] == 'deleted_from_cluster', collators)))
    node_logs_link = get_node_logs_link()

    return templates.TemplateResponse('collators.html', {'request': request,
                                                         'network_name': network,
                                                         'node_logs_link': node_logs_link,
                                                         'para_id': para_id,
                                                         'runtime': runtime,
                                                         'parachain_name': parachain_name,
                                                         'parachain_status': parachain_status,
                                                         'desired_candidates': str(desired_candidates),
                                                         'selected_stateful_set': statefulset,
                                                         'collators': collators,
                                                         'external_collator_count': external_collator_count,
                                                         'active_collator_count': active_collator_count,
                                                         'inactive_collator_count': inactive_collator_count,
                                                         'deleted_collator_count': deleted_collator_count,
                                                         'collator_stateful_sets': cluster_collator_stateful_set
                                                         })


@router.get("/runtime", response_class=HTMLResponse, include_in_schema=False)
async def get_runtime(
    request: Request
):
    return templates.TemplateResponse('runtime_info.html',
                                      dict(request=request,
                                           network=network,
                                           runtime=get_relay_runtime(),
                                           configuration=get_relay_active_configuration()))


@router.get("/parachains/{para_id}/runtime", response_class=HTMLResponse, include_in_schema=False)
async def get_runtime_parachain(
    request: Request,
    para_id: str = Path(description="ID of the parachain for which to get runtime info")
):
    return templates.TemplateResponse('runtime_info.html',
                                      dict(request=request,
                                           network=network,
                                           para_id=para_id,
                                           runtime=get_parachain_runtime(para_id)
                                           ))
