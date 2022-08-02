import logging

from fastapi import APIRouter, Path
from starlette.responses import JSONResponse, PlainTextResponse

from app.config.network_configuration import get_network
from app.lib.cron_tasks import list_cron_tasks, exec_cron_task

log = logging.getLogger('tasks_apis')

router = APIRouter()
network = get_network()


@router.get("/tasks/list")
async def get_tasks():
    return JSONResponse(list_cron_tasks())


@router.post("/tasks/execute/{job_id}")
async def get_tasks(
    job_id: str = Path(description="Job ID"),
):
    await exec_cron_task(job_id)
    return PlainTextResponse('OK')