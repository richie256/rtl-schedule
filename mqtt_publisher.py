
import os
import time
import datetime
import logging
import json
import paho.mqtt.publish as publish
from data_parser import ParseRTLData

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

def send_mqtt(topic, payload, host, port, auth):
    """Sends a message to an MQTT broker."""
    try:
        publish.single(topic, payload=payload, qos=0, hostname=host, port=port, auth=auth)
        _LOGGER.info(f"Published to MQTT topic '{topic}'")
    except Exception as ex:
        _LOGGER.error(f"MQTT Publish Failed: {ex}")

def main():
    """Main function to retrieve and publish bus schedule data."""
    try:
        stop_code = int(os.environ["STOP_CODE"])
        mqtt_host = os.environ["MQTT_HOST"]
        mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        mqtt_username = os.environ.get("MQTT_USERNAME")
        mqtt_password = os.environ.get("MQTT_PASSWORD")
    except (KeyError, ValueError) as e:
        _LOGGER.error(f"Environment variable error: {e}")
        return

    auth = None
    if mqtt_username and mqtt_password:
        auth = {'username': mqtt_username, 'password': mqtt_password}

    rtl_data = ParseRTLData()
    stop_id = rtl_data.get_stop_id(stop_code)

    if stop_id is None:
        _LOGGER.error(f"Could not find stop_id for stop_code {stop_code}")
        return

    while True:
        current_datetime = datetime.datetime.now().replace(microsecond=0)
        next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime)

        if next_stop_row is not None:
            difference = next_stop_row.arrival_datetime - current_datetime
            nbr_minutes, nbr_seconds = divmod(difference.total_seconds(), 60)

            payload = {
                'arrival_time': str(next_stop_row.arrival_time),
                'current_datetime': str(current_datetime),
                'nextstop_nbrmins': int(nbr_minutes),
                'nextstop_nbrsecs': int(nbr_seconds),
                'route_id': int(next_stop_row.route_id),
                'trip_headsign': str(next_stop_row.trip_headsign),
            }

            send_mqtt(f'schedule/bus_stop/{stop_code}', json.dumps(payload), mqtt_host, mqtt_port, auth)

        interval = 10 if is_rush_hour() else 60
        _LOGGER.info(f"Waiting for {interval} seconds...")
        time.sleep(interval)

if __name__ == "__main__":
    main()
