from time import sleep
from urllib import request


def wait_for_http_ready(url):
    for i in range(100):
        try:
            res = request.urlopen(url)
            if res.status == 200:
                break
        except Exception:
            pass
        sleep(1)