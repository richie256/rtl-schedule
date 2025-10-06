import os
from http_server import start_http_server
from mqtt_client import start_mqtt_client

if __name__ == "__main__":
    mode = os.environ.get("MODE", "http").lower()

    if mode == "http":
        start_http_server()
    elif mode == "mqtt":
        start_mqtt_client()
    else:
        print(f"Invalid mode: {mode}")