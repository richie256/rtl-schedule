from flask import Flask, jsonify
from flask_restful import Resource, Api
import paho.mqtt.publish as publish
import logging
import datetime
import os
import time
import json

from const import _LOGGER, RTL_MQTT_MODE, RTL_JSON_MS_MODE
from data_parser import ParseRTLData

# create logger with 'rtl-schedule'
_LOGGER.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('rtl-schedule.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
_LOGGER.addHandler(fh)
_LOGGER.addHandler(ch)

app = Flask(__name__)
api = Api(app)

run_mode = os.environ.get('RTL_MODE', RTL_JSON_MS_MODE).lower()

rtl_data = ParseRTLData()

class RtlScheduleNextStop(Resource):
    """ Get the next stop information in JSON format. """ 
    def get(self, stop_code):
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
            return jsonify(result)
        return jsonify({"error": "No more buses for today"})


def send_mqtt(topic, payload, host: str, port: int, auth):
    try:
        publish.single(topic, payload=payload, qos=0, hostname=host, port=port, auth=auth)
    except Exception as ex:
        _LOGGER.info(f"MQTT Publish Failed: {ex}")

class RtlScheduleNextStopMQTT:
    def __init__(self, stop_code: int):
        self.stop_code = stop_code
        self.stop_id = rtl_data.get_stop_id(self.stop_code)

    def retrieve_and_publish(self, host: str, port: int, authentication):
        current_datetime = datetime.datetime.now().replace(microsecond=0)
        next_stop_row = rtl_data.get_next_stop(self.stop_id, current_datetime)

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
            send_mqtt(f'schedule/bus_stop/{self.stop_code}', json.dumps(payload), host, port, authentication)

if run_mode == RTL_JSON_MS_MODE:
    api.add_resource(RtlScheduleNextStop, '/rtl_schedule/nextstop/<int:stop_code>')

if __name__ == '__main__':
    if run_mode == RTL_JSON_MS_MODE:
        app.run(host='0.0.0.0', port=80, debug=True)

    elif run_mode == RTL_MQTT_MODE:
        _LOGGER.info("MQTT mode...")
        mqtt_host = os.environ.get('MQTT_HOST')
        mqtt_port = int(os.environ.get('MQTT_PORT', 1883))
        stop_code = os.environ.get('RTL_STOP_CODE')

        if not all([mqtt_host, stop_code]):
            _LOGGER.error("MQTT_HOST and RTL_STOP_CODE must be set in MQTT mode.")
        else:
            stop_code = int(stop_code)
            auth = None
            if os.environ.get('MQTT_USERNAME') and os.environ.get('MQTT_PASSWORD'):
                auth = {'username': os.environ.get('MQTT_USERNAME'), 'password': os.environ.get('MQTT_PASSWORD')}

            rtl_mqtt = RtlScheduleNextStopMQTT(stop_code)
            while True:
                rtl_mqtt.retrieve_and_publish(mqtt_host, mqtt_port, auth)
                time.sleep(20)