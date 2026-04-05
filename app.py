import os
from const import _LOGGER
from config import config
from http_server import start_http_server
from mqtt_client import start_mqtt_client

if __name__ == "__main__":
    mode = os.environ.get("MODE", "http").lower()
    _LOGGER.info(f"Starting RTL Schedule in {mode.upper()} mode")

    if mode == "http":
        start_http_server()
    elif mode == "mqtt":
        start_mqtt_client()
    else:
        _LOGGER.error(f"Invalid mode: {mode}")