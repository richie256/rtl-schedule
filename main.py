from fastapi import FastAPI, BackgroundTasks
import paho.mqtt.publish as publish
import logging
import datetime
import os
import time
import json

from const import _LOGGER, RTL_MQTT_MODE, RTL_JSON_MS_MODE
from data_parser import ParseRTLData

app = FastAPI()

rtl_data = ParseRTLData()

@app.get("/rtl_schedule/nextstop/{stop_code}")
def get_next_stop(stop_code: int):
    stop_id = rtl_data.get_stop_id(stop_code)
    current_datetime = datetime.datetime.now().replace(microsecond=0)
    next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime)

    if next_stop_row is not None:
        difference = next_stop_row.arrival_datetime - current_datetime
        nbr_minutes, nbr_seconds = divmod(difference.total_seconds(), 60)

        result = {
            'nextstop_nbrmins': int(nbr_minutes),
            'nextstop_nbrsecs': int(nbr_seconds),
            'route_id': next_stop_row.route_id,
            'arrival_time': next_stop_row.arrival_time,
            'trip_headsign': next_stop_row.trip_headsign,
            'current_time': str(current_datetime.time()),
        }
        return result
    return {"error": "No more buses for today"}

def send_mqtt(topic, payload, host: str, port: int, auth):
    try:
        publish.single(topic, payload=payload, qos=0, hostname=host, port=port, auth=auth)
    except Exception as ex:
        _LOGGER.info(f"MQTT Publish Failed: {ex}")

def mqtt_publisher_task(stop_code: int, host: str, port: int, auth):
    stop_id = rtl_data.get_stop_id(stop_code)
    while True:
        current_datetime = datetime.datetime.now().replace(microsecond=0)
        next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime)

        if next_stop_row is not None:
            difference = next_stop_row.arrival_datetime - current_datetime
            nbr_minutes, nbr_seconds = divmod(difference.total_seconds(), 60)

            payload = {
                'arrival_time': next_stop_row.arrival_time,
                'current_datetime': str(current_datetime),
                'nextstop_nbrmins': int(nbr_minutes),
                'nextstop_nbrsecs': int(nbr_seconds),
                'route_id': next_stop_row.route_id,
                'trip_headsign': next_stop_row.trip_headsign,
            }

            _LOGGER.info(f"Publishing to MQTT: {payload}")
            send_mqtt(f'schedule/bus_stop/{stop_code}', json.dumps(payload), host, port, auth)
        time.sleep(20)

@app.post("/start-mqtt-publisher")
def start_mqtt_publisher(stop_code: int, mqtt_host: str, background_tasks: BackgroundTasks, mqtt_port: int = 1883, mqtt_username: str = None, mqtt_password: str = None):
    auth = None
    if mqtt_username and mqtt_password:
        auth = {'username': mqtt_username, 'password': mqtt_password}
    
    background_tasks.add_task(mqtt_publisher_task, stop_code, mqtt_host, mqtt_port, auth)
    return {"message": "MQTT publisher started in the background."}