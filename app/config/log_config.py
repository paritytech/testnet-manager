from os import environ

ROOT_LOG_LEVEL = environ.get('LOG_LEVEL', 'INFO').upper()

logger_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '%(levelprefix)s %(asctime)s - "%(request_line)s" %(status_code)s',
            "use_colors": True
        },
        "simple": {
            "fmt": '%(levelprefix)s %(asctime)s - "%(levelname)s" %(message)s',
            "use_colors": True
        },
    },
    "handlers": {
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stdout"
        }
    },
    "loggers": {
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False
        },
        "simple": {
            "handler": ["console"],
            "level": "INFO",
            "propagate": False
        },
        "kubernetes": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "level": ROOT_LOG_LEVEL,
        "handlers": ["console"]
    }
}
