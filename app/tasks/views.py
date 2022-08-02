from fastapi import APIRouter, Path, Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.config.network_configuration import get_network
from app.lib.cron_tasks import list_cron_tasks

router = APIRouter()
templates = Jinja2Templates(directory='app/templates')
network = get_network()


@router.get("/tasks",  response_class=HTMLResponse, include_in_schema=False)
async def tasks(
    request: Request,
):
    cron_tasks = list_cron_tasks()
    return templates.TemplateResponse('tasks.html', dict(request=request, network_name=network, tasks=cron_tasks))
