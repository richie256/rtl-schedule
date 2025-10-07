
import os
import time
import datetime
import logging
import json
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from pythonjsonlogger import jsonlogger

from data_parser import ParseRTLData

# Configure logging
_LOGGER = logging.getLogger("rtl-mqtt-publisher")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
_LOGGER.addHandler(logHandler)
_LOGGER.setLevel(logging.INFO)

def is_rush_hour(config: dict) -> bool:
    """Checks if the current time is during a weekday rush hour."""
    now = datetime.datetime.now()
    is_weekday = 0 <= now.weekday() <= 4  # Monday to Friday
    if not is_weekday:
        return False

    time_now = now.time()
    morning_rush_start = datetime.datetime.strptime(config["morning_rush_start"], "%H:%M").time()
    morning_rush_end = datetime.datetime.strptime(config["morning_rush_end"], "%H:%M").time()
    evening_rush_start = datetime.datetime.strptime(config["evening_rush_start"], "%H:%M").time()
    evening_rush_end = datetime.datetime.strptime(config["evening_rush_end"], "%H:%M").time()

    is_morning_rush = morning_rush_start <= time_now <= morning_rush_end
    is_evening_rush = evening_rush_start <= time_now <= evening_rush_end

    return is_morning_rush or is_evening_rush

def publish_hass_discovery_config(client, stop_code, discovery_prefix):
    """Publishes the Home Assistant discovery configuration for the bus stop sensor."""
    object_id = f"rtl_schedule_{stop_code}"
    discovery_topic = f"{discovery_prefix}/sensor/{object_id}/config"

    payload = {
        "name": f"Next Bus at Stop {stop_code}",
        "state_topic": "home/schedule/bus_stop",
        "value_template": f"{{% if value_json.stop_code == {stop_code} %}}{{{{ (value_json.nextstop_nbrmins + (value_json.nextstop_nbrsecs / 60)) | round(2) }}}}{{% else %}}{{{{ states('sensor.{object_id}') }}}}{{% endif %}}",
        "json_attributes_topic": "home/schedule/bus_stop",
        "json_attributes_template": f"{{% if value_json.stop_code == {stop_code} %}}{{{{ value_json | tojson }}}}{{% endif %}}",
        "unique_id": object_id,
        "icon": "mdi:bus-clock",
        "unit_of_measurement": "min",
        "device": {
            "identifiers": ["rtl_schedule"],
            "name": "RTL Schedule",
            "manufacturer": "RTL"
        }
    }

    client.publish(discovery_topic, json.dumps(payload), retain=True)
    _LOGGER.info("Published Home Assistant discovery configuration", extra={"topic": discovery_topic, "payload": payload})

def get_mqtt_config() -> dict:
    """Reads and returns the MQTT configuration from environment variables."""
    try:
        config = {
            "stop_code": int(os.environ["STOP_CODE"]),
            "mqtt_host": os.environ["MQTT_HOST"],
            "mqtt_port": int(os.environ.get("MQTT_PORT", 1883)),
            "mqtt_username": os.environ.get("MQTT_USERNAME"),
            "mqtt_password": os.environ.get("MQTT_PASSWORD"),
            "mqtt_use_tls": os.environ.get("MQTT_USE_TLS", "False").lower() == "true",
            "hass_discovery_enabled": os.environ.get("HASS_DISCOVERY_ENABLED", "False").lower() == "true",
            "hass_discovery_prefix": os.environ.get("HASS_DISCOVERY_PREFIX", "homeassistant"),
            "morning_rush_start": os.environ.get("MORNING_RUSH_START", "06:00"),
            "morning_rush_end": os.environ.get("MORNING_RUSH_END", "09:00"),
            "evening_rush_start": os.environ.get("EVENING_RUSH_START", "15:00"),
            "evening_rush_end": os.environ.get("EVENING_RUSH_END", "18:00"),
            "mqtt_refresh_topic": os.environ.get("MQTT_REFRESH_TOPIC", "rtl/schedule/refresh"),
        }
        return config
    except (KeyError, ValueError) as e:
        _LOGGER.error("Environment variable error", extra={"exception": str(e)})
        raise

def publish_schedule(client, rtl_data, stop_id, config):
    """Fetches and publishes the next bus stop information."""
    current_datetime = datetime.datetime.now().replace(microsecond=0)
    next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime)

    if next_stop_row is not None:
        difference = next_stop_row.arrival_datetime - current_datetime
        nbr_minutes, nbr_seconds = divmod(difference.total_seconds(), 60)

        payload = {
            'nextstop_nbrmins': int(nbr_minutes),
            'nextstop_nbrsecs': int(nbr_seconds),
            'route_id': int(next_stop_row.route_id),
            'arrival_time': str(next_stop_row.arrival_time),
            'trip_headsign': str(next_stop_row.trip_headsign),
            'current_time': str(current_datetime.time()),
            'stop_code': config['stop_code']
        }
        topic = 'home/schedule/bus_stop'
        client.publish(topic, json.dumps(payload))
        _LOGGER.info(f"Published to MQTT topic '{topic}'", extra={"topic": topic, "payload": payload})
    else:
        _LOGGER.info("No more buses for today.")

def start_mqtt_client():
    """Main function to retrieve and publish bus schedule data."""
    try:
        config = get_mqtt_config()
        rtl_data = ParseRTLData()
    except Exception as e:
        _LOGGER.error(f"Failed to initialize: {e}")
        return

    _LOGGER.info("Starting MQTT publisher", extra={"config": config})

    is_refresh_active = False
    refresh_end_time = None

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

    def on_message(client, userdata, msg):
        nonlocal is_refresh_active, refresh_end_time
        _LOGGER.info(f"Received message on topic {msg.topic}")
        if msg.topic == config["mqtt_refresh_topic"]:
            _LOGGER.info("Refresh action received")
            is_refresh_active = True
            refresh_end_time = datetime.datetime.now() + datetime.timedelta(minutes=10)
            publish_schedule(client, rtl_data, stop_id, config)

    client.on_message = on_message

    if config["mqtt_username"] and config["mqtt_password"]:
        client.username_pw_set(config["mqtt_username"], config["mqtt_password"])

    if config["mqtt_use_tls"]:
        client.tls_set()

    client.connect(config["mqtt_host"], config["mqtt_port"])
    client.subscribe(config["mqtt_refresh_topic"])
    client.loop_start()

    if config["hass_discovery_enabled"]:
        publish_hass_discovery_config(client, config["stop_code"], config["hass_discovery_prefix"])

    stop_id = rtl_data.get_stop_id(config['stop_code'])
    if stop_id is None:
        _LOGGER.error(f"Stop code {config['stop_code']} not found.")
        return

    try:
        while True:
            if is_refresh_active:
                if datetime.datetime.now() >= refresh_end_time:
                    is_refresh_active = False
                    _LOGGER.info("Refresh period ended")
                interval = 5
            else:
                interval = 10 if is_rush_hour(config) else 60
            
            publish_schedule(client, rtl_data, stop_id, config)
            
            _LOGGER.info(f"Waiting for {interval} seconds...", extra={"interval": interval})
            time.sleep(interval)
    finally:
        client.loop_stop()
        client.disconnect()
