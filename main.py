import logging
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse

from app.routers import views, apis
from app.config import log_config
from app.config.settings import settings
from kubernetes import config as kubernetes_config

app = FastAPI(title=settings.APP_NAME)
app.include_router(apis.router)
app.include_router(views.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup Logging
dictConfig(log_config.logger_config)
log = logging.getLogger(__name__)

# Connect to Kubernetes
try:
    kubernetes_config.load_incluster_config()
except:
    kubernetes_config.load_config()

@app.get("/health")
async def health():
    return PlainTextResponse('UP')
