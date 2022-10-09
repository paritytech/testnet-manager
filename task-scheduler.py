import logging
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse

from app.lib.cron_tasks import load_cron_tasks
from app.tasks import views, apis
from app.config import log_config
from app.config.settings import settings
from kubernetes import config as kubernetes_config


# Disable health check logs (https://stackoverflow.com/a/70810102)
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.args and len(record.args) >= 3 and record.args[2] != "/health"


app = FastAPI(title=settings.SCHEDULER_APP_NAME, on_startup=[load_cron_tasks])
app.include_router(apis.router)
app.include_router(views.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup Logging
dictConfig(log_config.logger_config)
log = logging.getLogger(__name__)
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# Connect to Kubernetes
try:
    kubernetes_config.load_incluster_config()
except:
    kubernetes_config.load_config()

@app.get("/health")
async def health():
    return PlainTextResponse('UP')
