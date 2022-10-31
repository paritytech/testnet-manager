from time import sleep
from urllib import request
import logging
from logging.config import dictConfig
from app.config import log_config

# Setup Logging
dictConfig(log_config.logger_config)
log = logging.getLogger(__name__)


def wait_for_http_ready(url):
    for i in range(100):
        print('.', end='')
        try:
            res = request.urlopen(url)
            if res.status == 200:
                break
        except Exception:
            pass
        sleep(1)