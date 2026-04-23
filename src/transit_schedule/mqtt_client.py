import datetime
import json
import logging
import threading
import time
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from pythonjsonlogger import json as jsonlogger

from transit_schedule.config import config
from transit_schedule.const import _LOGGER, DEFAULT_TIMEZONE, TRANSIT, TRANSLATIONS
from transit_schedule.data_parser import ParseTransitData

# Configure logging
if not _LOGGER.handlers:
    logHandler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(message)s")
    logHandler.setFormatter(formatter)
    _LOGGER.addHandler(logHandler)
    _LOGGER.setLevel(logging.INFO)

# Global flag to prevent multiple loops in the same process
_MQTT_LOOP_RUNNING = False
_MQTT_LOOP_LOCK = threading.Lock()

def get_translation():
    """Returns the translation dictionary for the configured language."""
    lang = config.language if config.language in TRANSLATIONS else "fr"
    return TRANSLATIONS[lang]

def publish_hass_discovery_config(client, stop_code, discovery_prefix):
    """Publishes the Home Assistant discovery configuration for the bus stop sensor."""
    object_id = f"transit_schedule_{stop_code}"
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
            "identifiers": ["transit_schedule"],
            "name": t["transit_schedule"],
            "manufacturer": TRANSIT
        }
    }

    client.publish(discovery_topic, json.dumps(payload), retain=True)
    _LOGGER.info("Published Home Assistant discovery configuration", extra={"topic": discovery_topic, "payload": payload})

def publish_schedule(client, transit_data, stop_id):
    """Fetches and publishes the next bus stop information."""
    current_datetime = datetime.datetime.now().replace(microsecond=0)
    next_stop_row = transit_data.get_next_stop(stop_id, current_datetime, stop_code=config.stop_code)
    
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
        return next_stop_row.arrival_datetime
    else:
        _LOGGER.info(t["no_more_buses"])
        return None

def on_message_callback(client, userdata, msg, refresh_event, t):
    _LOGGER.info(f"Received message on topic {msg.topic}")
    if msg.topic == config.mqtt_refresh_topic:
        _LOGGER.info(t["refresh_action_received"])
        refresh_event.set()
    elif msg.topic == config.mqtt_hass_status_topic:
        _LOGGER.info(t["hass_status_received"])
        if config.hass_discovery_enabled:
            publish_hass_discovery_config(client, config.stop_code, config.hass_discovery_prefix)
        refresh_event.set()

def start_mqtt_client():
    """Main function to retrieve and publish bus schedule data."""
    global _MQTT_LOOP_RUNNING

    with _MQTT_LOOP_LOCK:
        if _MQTT_LOOP_RUNNING:
            _LOGGER.warning("MQTT client loop is already running in this process. Skipping duplicate start.")
            return
        _MQTT_LOOP_RUNNING = True

    if config.stop_code is None:
        _LOGGER.error("STOP_CODE environment variable is required but missing or invalid.")
        return

    try:
        transit_data = ParseTransitData()
    except Exception as e:
        _LOGGER.error(f"Failed to initialize: {e}. Retrying in 30 seconds...")
        time.sleep(30)
        return

    _LOGGER.info("Starting MQTT publisher", extra={"config": config.to_dict()})
    
    t = get_translation()

    refresh_event = threading.Event()

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

    client.on_message = lambda c, u, m: on_message_callback(c, u, m, refresh_event, t)

    if config.mqtt_username and config.mqtt_password:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)

    if config.mqtt_use_tls:
        client.tls_set()

    client.connect(config.mqtt_host, config.mqtt_port)
    client.subscribe(config.mqtt_refresh_topic)
    client.subscribe(config.mqtt_hass_status_topic)
    client.loop_start()

    stop_id = transit_data.get_stop_id(config.stop_code)
    if stop_id is None:
        _LOGGER.error(f"Stop code {config.stop_code} not found.")
        return

    if config.hass_discovery_enabled:
        publish_hass_discovery_config(client, config.stop_code, config.hass_discovery_prefix)

    try:
        while True:
            try:
                # Clear any events that happened during the previous refresh 
                # to avoid immediate double-refreshes unless a new message arrives.
                refresh_event.clear()

                now = datetime.datetime.now()
                next_arrival = publish_schedule(client, transit_data, stop_id)
                
                if next_arrival:
                    # Wait until bus has passed + 10 seconds.
                    # This ensures we refresh as soon as the current "next bus" is gone.
                    seconds_to_wait = (next_arrival - now).total_seconds() + 10
                    # If bus is already in the past or very soon, wait at least 30s before next check
                    # to avoid tight loops if data hasn't updated yet.
                    interval = max(seconds_to_wait, 30)
                else:
                    # No bus found, wait 1 hour
                    interval = 3600
                
                _LOGGER.info(t["waiting_for"].format(interval=int(interval)), extra={"interval": int(interval)})
                
                # Wait for timeout OR event, with periodic heartbeat updates
                wait_until = time.time() + interval
                while time.time() < wait_until:
                    # Update heartbeat file for health check
                    try:
                        with open("/tmp/mqtt_heartbeat", "w") as f:
                            f.write(str(time.time()))
                    except Exception as e:
                        _LOGGER.error(f"Failed to update heartbeat file: {e}")
                    
                    remaining = wait_until - time.time()
                    if remaining <= 0:
                        break
                        
                    # Wait in chunks of 60s to keep heartbeat updated
                    if refresh_event.wait(timeout=min(remaining, 60)):
                        _LOGGER.info("Refresh event signaled, waking up...")
                        # We don't clear here anymore, we clear at the top of the loop
                        # to ensure we don't miss a signal during the refresh itself.
                        break
            except Exception as e:
                _LOGGER.error(f"Error in MQTT main loop: {e}. Retrying in 60 seconds...")
                time.sleep(60)
    finally:
        with _MQTT_LOOP_LOCK:
            _MQTT_LOOP_RUNNING = False
        client.loop_stop()
        client.disconnect()
