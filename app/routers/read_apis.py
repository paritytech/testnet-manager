import logging

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app.lib.log_utils import get_node_pod_logs
from app.lib.network_utils import list_substrate_nodes, list_validators, list_parachains, list_parachain_collators, \
    get_substrate_node
from app.lib.runtime_utils import get_relay_runtime, get_relay_active_configuration, get_parachain_runtime, \
    get_relaychain_metadata, get_parachain_metadata

log = logging.getLogger('router_read_apis')

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


@router.get("/runtime/metadata")
async def get_relaychain_runtime_metadata():
    return Response(content=get_relaychain_metadata(), media_type="application/octet-stream")


@router.get("/parachains/{para_id}/runtime")
async def get_runtime_parachain(
    para_id: str = Path(description="ID of the parachain for which to get runtime info")
):
    return JSONResponse(get_parachain_runtime(para_id))


@router.get("/parachains/{para_id}/runtime/metadata")
async def get_parachain_runtime_metadata(
    para_id: str = Path(description="ID of the parachain for which to get runtime metadata")
):
    return Response(content=get_parachain_metadata(para_id), media_type="application/octet-stream")
