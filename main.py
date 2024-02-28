import logging
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from kubernetes import config as kubernetes_config
from starlette.responses import JSONResponse

from app import __version__
from app.config import log_config
from app.config.network_configuration import sudo_mode
from app.config.settings import settings
from app.routers import views, read_apis, sudo_apis


# Disable health check logs (https://stackoverflow.com/a/70810102)
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.args and len(record.args) >= 3 and record.args[2] != "/health"

app = FastAPI(title=settings.APP_NAME, version=__version__)

app.include_router(read_apis.router)
if sudo_mode():
    app.include_router(sudo_apis.router)

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
    return JSONResponse({'status': 'UP', 'sudoMode': sudo_mode})
