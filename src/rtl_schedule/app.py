import os

from rtl_schedule.const import _LOGGER
from rtl_schedule.http_server import start_http_server
from rtl_schedule.mqtt_client import start_mqtt_client


def main():
    mode = os.environ.get("MODE", "http").lower()
    _LOGGER.info(f"Starting RTL Schedule in {mode.upper()} mode")

    if mode == "http":
        start_http_server()
    elif mode == "mqtt":
        start_mqtt_client()
    else:
        _LOGGER.error(f"Invalid mode: {mode}")

if __name__ == "__main__":
    main()