import os
import time
import datetime
import logging
import json
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from pythonjsonlogger import json as jsonlogger
from zoneinfo import ZoneInfo

from data_parser import ParseRTLData
from const import _LOGGER, DEFAULT_TIMEZONE, LANGUAGE, TRANSLATIONS
from config import config

# Configure logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
_LOGGER.addHandler(logHandler)
_LOGGER.setLevel(logging.INFO)

def get_translation():
    """Returns the translation dictionary for the configured language."""
    lang = config.language if config.language in TRANSLATIONS else "fr"
    return TRANSLATIONS[lang]

def is_rush_hour() -> bool:
    """Checks if the current time is during a weekday rush hour."""
    now = datetime.datetime.now()
    is_weekday = 0 <= now.weekday() <= 4  # Monday to Friday
    if not is_weekday:
        return False

    time_now = now.time()
    morning_rush_start = datetime.datetime.strptime(config.morning_rush_start, "%H:%M").time()
    morning_rush_end = datetime.datetime.strptime(config.morning_rush_end, "%H:%M").time()
    evening_rush_start = datetime.datetime.strptime(config.evening_rush_start, "%H:%M").time()
    evening_rush_end = datetime.datetime.strptime(config.evening_rush_end, "%H:%M").time()

    is_morning_rush = morning_rush_start <= time_now <= morning_rush_end
    is_evening_rush = evening_rush_start <= time_now <= evening_rush_end

    return is_morning_rush or is_evening_rush

def publish_hass_discovery_config(client, stop_code, discovery_prefix):
    """Publishes the Home Assistant discovery configuration for the bus stop sensor."""
    object_id = f"rtl_schedule_{stop_code}"
    discovery_topic = f"{discovery_prefix}/sensor/{object_id}/config"
    state_topic = config.mqtt_state_topic
    
    t = get_translation()

    payload = {
        "name": t["next_bus_at_stop"].format(stop_code=stop_code),
        "state_topic": state_topic,
        "value_template": "{{ value_json.arrival_datetime_iso }}",
        "json_attributes_topic": state_topic,
        "unique_id": object_id,
        "icon": "mdi:bus-clock",
        "device_class": "timestamp",
        "json_attributes_template": "{{ {'trip_headsign': value_json.trip_headsign} | tojson }}",
        "device": {
            "identifiers": ["rtl_schedule"],
            "name": t["rtl_schedule"],
            "manufacturer": "RTL"
        }
    }

    client.publish(discovery_topic, json.dumps(payload), retain=True)
    _LOGGER.info("Published Home Assistant discovery configuration", extra={"topic": discovery_topic, "payload": payload})

def publish_schedule(client, rtl_data, stop_id):
    """Fetches and publishes the next bus stop information."""
    current_datetime = datetime.datetime.now().replace(microsecond=0)
    next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime, stop_code=config.stop_code)
    
    t = get_translation()

    if next_stop_row is not None:
        difference = next_stop_row.arrival_datetime - current_datetime
        nbr_minutes, nbr_seconds = divmod(difference.total_seconds(), 60)

        # Localize retrieve_method
        method = str(next_stop_row.retrieve_method)
        if method == "GTFS":
            localized_method = t["gtfs"]
        elif method == "live scraper":
            localized_method = t["live_scraper"]
        else:
            localized_method = method

        payload = {
            'nextstop_nbrmins': int(nbr_minutes),
            'nextstop_nbrsecs': int(nbr_seconds),
            'route_id': str(next_stop_row.route_id),
            'arrival_time': str(next_stop_row.arrival_time),
            'arrival_datetime_iso': next_stop_row.arrival_datetime.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE)).isoformat(),
            'trip_headsign': str(next_stop_row.trip_headsign),
            'current_time': str(current_datetime.time()),
            'stop_code': config.stop_code,
            'retrieve_method': localized_method
        }
        topic = config.mqtt_state_topic
        client.publish(topic, json.dumps(payload), retain=True)
        _LOGGER.info(f"Published to MQTT topic '{topic}'", extra={"topic": topic, "payload": payload})
    else:
        _LOGGER.info(t["no_more_buses"])

def start_mqtt_client():
    """Main function to retrieve and publish bus schedule data."""
    if config.stop_code is None:
        _LOGGER.error("STOP_CODE environment variable is required but missing or invalid.")
        return

    try:
        rtl_data = ParseRTLData()
    except Exception as e:
        _LOGGER.error(f"Failed to initialize: {e}")
        return

    _LOGGER.info("Starting MQTT publisher", extra={"config": config.to_dict()})
    
    t = get_translation()

    is_refresh_active = False
    refresh_end_time = None
    last_discovery_publish = 0

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

    def on_message(client, userdata, msg):
        nonlocal is_refresh_active, refresh_end_time
        _LOGGER.info(f"Received message on topic {msg.topic}")
        if msg.topic == config.mqtt_refresh_topic:
            _LOGGER.info(t["refresh_action_received"])
            is_refresh_active = True
            refresh_end_time = datetime.datetime.now() + datetime.timedelta(minutes=10)
            publish_schedule(client, rtl_data, stop_id)

    client.on_message = on_message

    if config.mqtt_username and config.mqtt_password:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)

    if config.mqtt_use_tls:
        client.tls_set()

    client.connect(config.mqtt_host, config.mqtt_port)
    client.subscribe(config.mqtt_refresh_topic)
    client.loop_start()

    stop_id = rtl_data.get_stop_id(config.stop_code)
    if stop_id is None:
        _LOGGER.error(f"Stop code {config.stop_code} not found.")
        return

    try:
        while True:
            # Re-publish discovery config every 12 hours
            current_time = time.time()
            if config.hass_discovery_enabled and (current_time - last_discovery_publish >= 12 * 3600):
                publish_hass_discovery_config(client, config.stop_code, config.hass_discovery_prefix)
                last_discovery_publish = current_time

            if is_refresh_active:
                if datetime.datetime.now() >= refresh_end_time:
                    is_refresh_active = False
                    _LOGGER.info(t["refresh_period_ended"])
                interval = 5
            else:
                interval = 10 if is_rush_hour() else 60
            
            publish_schedule(client, rtl_data, stop_id)
            
            # Update heartbeat file for health check
            try:
                with open("/tmp/mqtt_heartbeat", "w") as f:
                    f.write(str(time.time()))
            except Exception as e:
                _LOGGER.error(f"Failed to update heartbeat file: {e}")
            
            _LOGGER.info(t["waiting_for"].format(interval=interval), extra={"interval": interval})
            time.sleep(interval)
    finally:
        client.loop_stop()
        client.disconnect()
