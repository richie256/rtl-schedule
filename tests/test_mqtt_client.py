import datetime
import json
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from rtl_schedule.const import DEFAULT_TIMEZONE, LANGUAGE, TRANSLATIONS
from rtl_schedule.mqtt_client import is_rush_hour, publish_hass_discovery_config, publish_schedule


# Mock config to be used in tests
class MockConfig:
    def __init__(self):
        self.morning_rush_start = "06:00"
        self.morning_rush_end = "09:00"
        self.evening_rush_start = "15:00"
        self.evening_rush_end = "18:00"
        self.stop_code = 12345
        self.mqtt_state_topic = "home/transit/bus/stop_12345"
        self.language = LANGUAGE

def get_t():
    lang = LANGUAGE if LANGUAGE in TRANSLATIONS else "fr"
    return TRANSLATIONS[lang]

@patch('rtl_schedule.mqtt_client.config')
@freeze_time("2023-03-15 07:30:00")
def test_is_rush_hour_morning(mock_cfg_inst):
    mock_cfg_inst.morning_rush_start = "06:00"
    mock_cfg_inst.morning_rush_end = "09:00"
    mock_cfg_inst.evening_rush_start = "15:00"
    mock_cfg_inst.evening_rush_end = "18:00"
    assert is_rush_hour()

@patch('rtl_schedule.mqtt_client.config')
@freeze_time("2023-03-15 16:30:00")
def test_is_rush_hour_evening(mock_cfg_inst):
    mock_cfg_inst.morning_rush_start = "06:00"
    mock_cfg_inst.morning_rush_end = "09:00"
    mock_cfg_inst.evening_rush_start = "15:00"
    mock_cfg_inst.evening_rush_end = "18:00"
    assert is_rush_hour()

@patch('rtl_schedule.mqtt_client.config')
@freeze_time("2023-03-15 12:00:00")
def test_is_not_rush_hour_midday(mock_cfg_inst):
    mock_cfg_inst.morning_rush_start = "06:00"
    mock_cfg_inst.morning_rush_end = "09:00"
    mock_cfg_inst.evening_rush_start = "15:00"
    mock_cfg_inst.evening_rush_end = "18:00"
    assert not is_rush_hour()

@patch('rtl_schedule.mqtt_client.config')
@freeze_time("2023-03-18 08:00:00")
def test_is_not_rush_hour_weekend(mock_cfg_inst):
    mock_cfg_inst.morning_rush_start = "06:00"
    mock_cfg_inst.morning_rush_end = "09:00"
    mock_cfg_inst.evening_rush_start = "15:00"
    mock_cfg_inst.evening_rush_end = "18:00"
    assert not is_rush_hour()

@patch('rtl_schedule.mqtt_client.config')
def test_publish_hass_discovery_config(mock_cfg_inst):
    mock_cfg_inst.mqtt_state_topic = "home/transit/bus/stop_12345"
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
    assert payload_dict['state_topic'] == "home/transit/bus/stop_12345"
    assert "trip_headsign" in payload_dict['json_attributes_template']

@patch('rtl_schedule.mqtt_client.config')
@freeze_time("2023-03-15 07:30:00")
def test_publish_schedule(mock_cfg_inst):
    mock_cfg_inst.stop_code = 12345
    mock_cfg_inst.mqtt_state_topic = "home/transit/bus/stop_12345"
    mock_cfg_inst.language = LANGUAGE

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
    
    publish_schedule(mock_client, mock_rtl_data, "stop_id_123")
    
    mock_client.publish.assert_called_once()
    args, kwargs = mock_client.publish.call_args
    
    assert kwargs.get('retain') is True
    payload = json.loads(args[1])
    assert payload['arrival_datetime_iso'] == arrival_dt.replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE)).isoformat()
    assert payload['nextstop_nbrmins'] == 15
    assert payload['nextstop_nbrsecs'] == 0
    assert payload['retrieve_method'] == t["gtfs"]

@patch('rtl_schedule.mqtt_client.config')
def test_publish_schedule_live_scraper(mock_cfg_inst):
    mock_cfg_inst.stop_code = 12345
    mock_cfg_inst.mqtt_state_topic = "topic"
    mock_cfg_inst.language = "fr"

    mock_client = MagicMock()
    mock_rtl_data = MagicMock()
    
    mock_next_stop = MagicMock()
    mock_next_stop.arrival_datetime = datetime.datetime.now() + datetime.timedelta(minutes=5)
    mock_next_stop.retrieve_method = "live scraper"
    mock_rtl_data.get_next_stop.return_value = mock_next_stop
    
    publish_schedule(mock_client, mock_rtl_data, "stop_id")
    
    args, kwargs = mock_client.publish.call_args
    assert kwargs.get('retain') is True
    payload = json.loads(args[1])
    assert payload['retrieve_method'] == TRANSLATIONS["fr"]["live_scraper"]

@patch('rtl_schedule.mqtt_client.config')
def test_publish_schedule_no_bus(mock_cfg_inst):
    mock_cfg_inst.stop_code = 12345
    mock_cfg_inst.mqtt_state_topic = "topic"

    mock_client = MagicMock()
    mock_rtl_data = MagicMock()
    mock_rtl_data.get_next_stop.return_value = None
    
    with patch('rtl_schedule.mqtt_client._LOGGER') as mock_logger:
        publish_schedule(mock_client, mock_rtl_data, "stop_id")
        mock_client.publish.assert_not_called()

@patch('rtl_schedule.mqtt_client.config')
def test_start_mqtt_client_missing_stop_code(mock_cfg_inst):
    mock_cfg_inst.stop_code = None
    with patch('rtl_schedule.mqtt_client._LOGGER') as mock_logger:
        from rtl_schedule.mqtt_client import start_mqtt_client
        start_mqtt_client()
        mock_logger.error.assert_called_with("STOP_CODE environment variable is required but missing or invalid.")

@patch('rtl_schedule.mqtt_client.config')
@patch('rtl_schedule.mqtt_client.mqtt.Client')
@patch('rtl_schedule.mqtt_client.ParseRTLData')
@patch('rtl_schedule.mqtt_client.time.sleep', side_effect=KeyboardInterrupt)
def test_start_mqtt_client_loop(mock_sleep, mock_rtl_parser, mock_mqtt_client, mock_cfg_inst):
    mock_cfg_inst.stop_code = "12345"
    mock_cfg_inst.mqtt_host = "localhost"
    mock_cfg_inst.mqtt_port = 1883
    mock_cfg_inst.mqtt_username = "user"
    mock_cfg_inst.mqtt_password = "pass"
    mock_cfg_inst.mqtt_use_tls = False
    mock_cfg_inst.mqtt_refresh_topic = "refresh"
    mock_cfg_inst.hass_discovery_enabled = False
    mock_cfg_inst.morning_rush_start = "06:00"
    mock_cfg_inst.morning_rush_end = "09:00"
    mock_cfg_inst.evening_rush_start = "15:00"
    mock_cfg_inst.evening_rush_end = "18:00"
    mock_cfg_inst.language = "fr"
    
    mock_parser_inst = mock_rtl_parser.return_value
    mock_parser_inst.get_stop_id.return_value = "stop_id_123"
    mock_parser_inst.get_next_stop.return_value = None
    
    from rtl_schedule.mqtt_client import start_mqtt_client
    try:
        start_mqtt_client()
    except KeyboardInterrupt:
        pass
    
    mock_mqtt_client.return_value.connect.assert_called_with("localhost", 1883)
    mock_mqtt_client.return_value.loop_start.assert_called()
