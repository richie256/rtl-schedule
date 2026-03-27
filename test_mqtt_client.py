import pytest
from unittest.mock import patch, MagicMock
import datetime
import json
from zoneinfo import ZoneInfo

from mqtt_client import is_rush_hour, publish_hass_discovery_config, publish_schedule
from freezegun import freeze_time
from const import DEFAULT_TIMEZONE, TRANSLATIONS, LANGUAGE

mock_config = {
    "morning_rush_start": "06:00",
    "morning_rush_end": "09:00",
    "evening_rush_start": "15:00",
    "evening_rush_end": "18:00",
    "stop_code": 12345,
    "mqtt_state_topic": "home/transit/bus/stop_12345"
}

def get_t():
    lang = LANGUAGE if LANGUAGE in TRANSLATIONS else "fr"
    return TRANSLATIONS[lang]

@freeze_time("2023-03-15 07:30:00")
def test_is_rush_hour_morning():
    assert is_rush_hour(mock_config)

@freeze_time("2023-03-15 16:30:00")
def test_is_rush_hour_evening():
    assert is_rush_hour(mock_config)

@freeze_time("2023-03-15 12:00:00")
def test_is_not_rush_hour_midday():
    assert not is_rush_hour(mock_config)

@freeze_time("2023-03-18 08:00:00")
def test_is_not_rush_hour_weekend():
    assert not is_rush_hour(mock_config)

def test_publish_hass_discovery_config():
    mock_client = MagicMock()
    stop_code = 12345
    discovery_prefix = "homeassistant"
    
    t = get_t()

    publish_hass_discovery_config(mock_client, stop_code, discovery_prefix)

    expected_topic = f"{discovery_prefix}/sensor/rtl_schedule_{stop_code}/config"
    
    mock_client.publish.assert_called_once()
    
    args, kwargs = mock_client.publish.call_args
    
    assert args[0] == expected_topic
    assert kwargs['retain'] is True

    payload_dict = json.loads(args[1])
    assert payload_dict['name'] == t["next_bus_at_stop"].format(stop_code=stop_code)
    assert payload_dict['unique_id'] == f"rtl_schedule_{stop_code}"
    assert payload_dict['state_topic'] == f"home/transit/bus/stop_{stop_code}"
    assert payload_dict['json_attributes_topic'] == f"home/transit/bus/stop_{stop_code}"
    assert payload_dict['device_class'] == 'timestamp'
    assert payload_dict['value_template'] == '{{ value_json.arrival_datetime_iso }}'
    assert 'unit_of_measurement' not in payload_dict

@freeze_time("2023-03-15 07:30:00")
def test_publish_schedule():
    mock_client = MagicMock()
    mock_rtl_data = MagicMock()
    
    t = get_t()
    
    arrival_dt = datetime.datetime(2023, 3, 15, 7, 45, 0)
    mock_next_stop = MagicMock()
    mock_next_stop.arrival_datetime = arrival_dt
    mock_next_stop.arrival_time = "07:45:00"
    mock_next_stop.route_id = "123"
    mock_next_stop.trip_headsign = "Terminus Panama"
    mock_next_stop.retrieve_method = "GTFS"
    
    mock_rtl_data.get_next_stop.return_value = mock_next_stop
    
    publish_schedule(mock_client, mock_rtl_data, "stop_id_123", mock_config)
    
    mock_client.publish.assert_called_once()
    args, _ = mock_client.publish.call_args
    
    payload = json.loads(args[1])
    assert payload['arrival_datetime_iso'] == arrival_dt.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE)).isoformat()
    assert payload['nextstop_nbrmins'] == 15
    assert payload['nextstop_nbrsecs'] == 0
    assert payload['retrieve_method'] == t["gtfs"]
