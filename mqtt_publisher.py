
import os
import time
import datetime
import logging
import json
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("rtl-mqtt-publisher")

def is_rush_hour():
    """Checks if the current time is during a weekday rush hour."""
    now = datetime.datetime.now()
    is_weekday = 0 <= now.weekday() <= 4  # Monday to Friday
    if not is_weekday:
        return False

    time_now = now.time()
    morning_rush_start = datetime.time(6, 0)
    morning_rush_end = datetime.time(9, 0)
    evening_rush_start = datetime.time(15, 0)
    evening_rush_end = datetime.time(18, 0)

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
        "value_template": f"{{% if value_json.stop_code == {stop_code} %}}{{ (value_json.nextstop_nbrmins + (value_json.nextstop_nbrsecs / 60)) | round(2) }}{{% else %}}{{ states('sensor.{object_id}') }}{{% endif %}}",
        "json_attributes_topic": "home/schedule/bus_stop",
        "json_attributes_template": f"{{% if value_json.stop_code == {stop_code} %}}{{ value_json | tojson }}{{% endif %}}",
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
    _LOGGER.info(f"Published Home Assistant discovery configuration to '{discovery_topic}'")

def main():
    """Main function to retrieve and publish bus schedule data."""
    try:
        stop_code = int(os.environ["STOP_CODE"])
        mqtt_host = os.environ["MQTT_HOST"]
        mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        mqtt_username = os.environ.get("MQTT_USERNAME")
        mqtt_password = os.environ.get("MQTT_PASSWORD")
        mqtt_use_tls = os.environ.get("MQTT_USE_TLS", "False").lower() == "true"
        hass_discovery_enabled = os.environ.get("HASS_DISCOVERY_ENABLED", "False").lower() == "true"
        hass_discovery_prefix = os.environ.get("HASS_DISCOVERY_PREFIX", "homeassistant")

    except (KeyError, ValueError) as e:
        _LOGGER.error(f"Environment variable error: {e}")
        return

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)

    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)

    if mqtt_use_tls:
        client.tls_set()

    client.connect(mqtt_host, mqtt_port)
    client.loop_start()

    if hass_discovery_enabled:
        publish_hass_discovery_config(client, stop_code, hass_discovery_prefix)

    web_service_url = f"http://web:80/rtl_schedule/nextstop/{stop_code}"

    try:
        while True:
            try:
                response = requests.get(web_service_url)
                response.raise_for_status()  # Raise an exception for bad status codes
                payload = response.json()

                payload['stop_code'] = stop_code

                topic = 'home/schedule/bus_stop'
                client.publish(topic, json.dumps(payload))
                _LOGGER.info(f"Published to MQTT topic '{topic}'")

            except requests.exceptions.RequestException as e:
                _LOGGER.error(f"Error calling web service: {e}")

            interval = 10 if is_rush_hour() else 60
            _LOGGER.info(f"Waiting for {interval} seconds...")
            time.sleep(interval)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
