import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter, Path, Query, HTTPException, File, UploadFile
from starlette.responses import JSONResponse, PlainTextResponse
from substrateinterface import Keypair

from app.config.network_configuration import network_sudo_seed
from app.lib.balance_utils import teleport_funds
from app.lib.kubernetes_client import list_validator_stateful_sets
from app.lib.log_utils import get_node_pod_logs
from app.lib.network_utils import list_substrate_nodes, list_validators, list_parachains, list_parachain_collators, \
    register_statefulset_validators, deregister_statefulset_validators, deregister_validator_addresses, \
    rotate_nodes_session_keys, register_statefulset_collators, onboard_parachain_by_id, \
    offboard_parachain_by_id, deregister_statefulset_collators, get_substrate_node, \
    register_validator_nodes, register_validator_addresses, deregister_validator_nodes, register_collator_nodes, \
    deregister_collator_nodes, add_invulnerable_collators, remove_invulnerable_collators, \
    set_collator_nodes_keys_on_chain
from app.lib.runtime_utils import get_relay_runtime, get_relay_active_configuration, update_relay_configuration, \
    get_parachain_runtime, runtime_upgrade
from app.lib.substrate import get_relay_chain_client
from app.lib.parachain_manager import parachain_runtime_upgrade

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


@router.get("/nodes/{node_name}/logs", response_class=PlainTextResponse, )
async def get_node_logs(
    node_name: str = Path(description="Name of the node"),
):
    node_logs = await get_node_pod_logs(node_name)
    return PlainTextResponse(node_logs)


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


@router.get("/runtime")
async def get_runtime():
    return JSONResponse(get_relay_runtime())


@router.get("/runtime/configuration")
async def get_runtime_configuration():
    return JSONResponse(get_relay_active_configuration())


@router.post("/runtime/configuration")
async def update_runtime_configuration(new_configuration_keys: Dict[str, Any]):
    for key, value in new_configuration_keys.items():
        status, message = update_relay_configuration(key, value)
        if not status:
            raise HTTPException(status_code=500, detail=message)
    return PlainTextResponse("OK")


@router.get("/parachains/{para_id}/runtime")
async def get_runtime_parachain(
    para_id: str = Path(description="ID of the parachain for which to get runtime info")
):
    return JSONResponse(get_parachain_runtime(para_id))


@router.post("/validators/register")
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


@router.post("/validators/deregister")
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


@router.post("/parachains/onboard")
async def onboard_parachains(
    para_id: list[str] = Query(description="Parachain ID(s) to onboard")
):
    parachains = list_parachains()
    for id in para_id:
        # Onboard parachain if not currently active
        if id not in parachains:
            asyncio.create_task(onboard_parachain_by_id(id))
    return PlainTextResponse('OK')


@router.post("/parachains/offboard")
async def offboard_parachains(
    para_id: list[str] = Query(description="Parachain ID(s) to offboard")
):
    parachains = list_parachains()
    for id in para_id:
        # Offboard parachain if currently active
        if id in parachains:
            asyncio.create_task(offboard_parachain_by_id(id))
    return PlainTextResponse('OK')


@router.post("/collators/{para_id}/register")
async def register_collators(
    para_id: str = Path(description="Parachain ID on which to register collators"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet to register"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be registered")
):
    if statefulset:
        asyncio.create_task(register_statefulset_collators(para_id, statefulset))
    if node:
        chain = get_substrate_node(node[0])["chain"]
        ss58_format = get_substrate_node(node[0])["ss58_format"]
        asyncio.create_task(register_collator_nodes(chain, node, ss58_format))
    return PlainTextResponse('OK')


@router.post("/collators/{para_id}/deregister")
async def deregister_collators(
    para_id: str = Path(description="Parachain ID on which to deregister collators"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet to deregister"),
    node: list[str] = Query(default=[], description="Name of the node(s) to be deregistered")
):
    if statefulset:
        asyncio.create_task(deregister_statefulset_collators(para_id, statefulset))
    if node:
        chain = get_substrate_node(node[0])["chain"]
        ss58_format = get_substrate_node(node[0])["ss58_format"]
        asyncio.create_task(deregister_collator_nodes(chain, node, ss58_format))
    return PlainTextResponse('OK')


@router.post("/collators/{para_id}/add_invulnerables")
async def add_invulnerables(
    para_id: str = Path(description="Parachain ID"),
    address: list[str] = Query(default=[], description="Address(es) to be added as invulnerables"),
    node: list[str] = Query(default=[], description="Collator node(s) be added as invulnerables on the parachain")
):
    if node or address:
        asyncio.create_task(add_invulnerable_collators(para_id, node, address))
    return PlainTextResponse('OK')


@router.post("/collators/{para_id}/remove_invulnerables")
async def remove_invulnerables(
    para_id: str = Path(description="Parachain ID"),
    address: list[str] = Query(default=[], description="Address(es) to removed from invulnerables"),
    node: list[str] = Query(default=[], description="Collator node(s) to be removed as invulnerables on the parachain")
):
    if node or address:
        asyncio.create_task(remove_invulnerable_collators(para_id, node, address))
    return PlainTextResponse('OK')


@router.post("/collators/set_on_chain_keys")
async def set_on_chain_keys(
    para_id: str = Query(description="Parachain ID"),
    node: list[str] = Query(default=[], description="Collator node(s) for which to set keys on chain"),
    statefulset: str = Query(default=None, description="Name of the StatefulSet for which to set keys on chain"),
):
    if node:
        asyncio.create_task(set_collator_nodes_keys_on_chain(para_id, node,statefulset))
    return PlainTextResponse('OK')


@router.post("/xcm/teleport_funds")
async def teleport_funds_from_sudo(
    para_id: int = Query(description="Parachain ID"),
    account: list[str] = Query(description="Account(s) to fund on the Parachain (in relay-chain SS58 format)"),
    amount: int = Query(default=1000000000000, description="Amount to transfer to each accounts")
):
    relay_chain_client = get_relay_chain_client()
    from_account_keypair = Keypair.create_from_seed(network_sudo_seed())
    teleport_funds(relay_chain_client, from_account_keypair, para_id, account, amount)
    return PlainTextResponse('OK')


@router.post("/parachains/{para_id}/runtime/upgrade")
async def parachain_upload_runtime_and_upgrade(
    runtime: UploadFile = File(description="File with runtime: *.compact.compressed.wasm"),
    para_id: str = Path(description="Parachain ID on which to upgrade runtime")
):
    runtime_name = runtime.filename.split('.')[0]
    runtime_bytes = await runtime.read()
    status, txt = parachain_runtime_upgrade(runtime_name, para_id, runtime_bytes)
    if not status:
        raise HTTPException(status_code=500, detail=txt)
    else:
        return PlainTextResponse(txt)


@router.post("/runtime/upgrade")
async def upload_runtime_and_upgrade(
    runtime: UploadFile = File(description="File with runtime: *.compact.compressed.wasm"),
    schedule_blocks_wait: int = Query(description="Setup scheduler to delay execution of the runtime by a number of blocks", default=None)
):
    runtime_name = runtime.filename.split('.')[0]
    runtime_bytes = await runtime.read()
    status, txt = runtime_upgrade(runtime_name, runtime_bytes, schedule_blocks_wait)
    if not status:
        raise HTTPException(status_code=500, detail=txt)
    else:
        return PlainTextResponse(txt)
