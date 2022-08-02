import asyncio
import logging

from fastapi import APIRouter, Path, Query, HTTPException
from starlette.responses import JSONResponse, PlainTextResponse

from app.lib.kubernetes_client import list_validator_stateful_sets
from app.lib.network_utils import list_substrate_nodes, list_validators, list_parachains, list_parachain_collators, \
    register_statefulset_validators, deregister_statefulset_validators, deregister_validator_addresses, \
    rotate_nodes_session_keys, register_statefulset_collators, onboard_parachain_by_id, \
    offboard_parachain_by_id, deregister_statefulset_collators, get_substrate_node, \
    register_validator_nodes, register_validator_addresses, deregister_validator_nodes, register_collator_nodes, \
    deregister_collator_nodes

log = logging.getLogger('router_apis')

router = APIRouter(prefix="/api")


@router.get("/nodes")
async def get_nodes(
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    return JSONResponse(list_substrate_nodes(statefulset))


@router.get("/nodes/{node_name}")
async def get_nodes(
    node_name: str = Path(description="Name of the node"),
):
    return JSONResponse(get_substrate_node(node_name))


@router.get("/validators")
async def get_validators(
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    return JSONResponse(list_validators(statefulset))


@router.get("/parachains")
async def get_parachains():
    return JSONResponse(list_parachains())


@router.get("/collators/{para_id}")
async def get_collators(
    para_id: str = Path(description="ID of the parachain for which to get collators"),
    statefulset: str = Query(default="", description="To restrict the displayed nodes to a single StatefulSet")
):
    return JSONResponse(list_parachain_collators(para_id, statefulset))


@router.post("/register_validators")
async def register_validators(
    statefulset: str = Query(default=None, description="Name of the StatefulSet containing the nodes to be registered"),
    address: list[str] = Query(default=[], description="Address(es) to be deregistered"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be registered")
):
    if statefulset:
        asyncio.create_task(register_statefulset_validators(statefulset))
    if address:
        asyncio.create_task(register_validator_addresses(address))
    if node:
        asyncio.create_task(register_validator_nodes(node))
    return PlainTextResponse('OK')


@router.post("/deregister_validators")
async def deregister_validators(
    statefulset: str = Query(default=None, description="Name of the StatefulSet containing the nodes to be deregistered"),
    address: list[str] = Query(default=None, description="Address(es) to be deregistered"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be deregistered")
):
    if statefulset:
        asyncio.create_task(deregister_statefulset_validators(statefulset))
    if address:
        asyncio.create_task(deregister_validator_addresses(address))
    if node:
        asyncio.create_task(deregister_validator_nodes(node))
    return PlainTextResponse('OK')


@router.post("/rotate_session_keys")
async def rotate_session_keys(
    all: bool = Query(default=False, description="Set to true to rotate all nodes session keys"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet for which to rotate session keys"),
    node: list[str] = Query(default=[], description="Name of the node(s) for which to rotate session keys")
):
    if all:
        validator_stateful_sets = list_validator_stateful_sets()
        for validator_stateful_set in validator_stateful_sets:
            asyncio.create_task(rotate_nodes_session_keys(validator_stateful_set))
    if statefulset:
        asyncio.create_task(rotate_nodes_session_keys(statefulset))
    if node:
        log.info(F'Rotating session keys node: {node} (not implemented)')
        raise HTTPException(status_code=404, detail="Feature not implemented yet")


@router.post("/onboard_parachain/{para_id}")
async def onboard_parachain(
    para_id: str = Path(description="Parachain ID to onboard")
):
    asyncio.create_task(onboard_parachain_by_id(para_id))
    return PlainTextResponse('OK')


@router.post("/offboard_parachain/{para_id}")
async def offboard_parachain(
    para_id: str = Path(description="Parachain ID to offboard")
):
    asyncio.create_task(offboard_parachain_by_id(para_id))
    return PlainTextResponse('OK')


@router.post("/register_collators/{para_id}")
async def register_collators(
    para_id: str = Path(description="Parachain ID on which to register collators"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet to register"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be registered")
):
    if statefulset:
        asyncio.create_task(register_statefulset_collators(para_id, statefulset))
    if node:
        chain = get_substrate_node(node[0])["chain"]
        asyncio.create_task(register_collator_nodes(chain, node))


@router.post("/deregister_collators/{para_id}")
async def deregister_collators(
    para_id: str = Path(description="Parachain ID on which to deregister collators"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet to deregister"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be deregistered")
):
    if statefulset:
        asyncio.create_task(deregister_statefulset_collators(para_id, statefulset))
    if node:
        chain = get_substrate_node(node[0])["chain"]
        asyncio.create_task(deregister_collator_nodes(chain, node))
