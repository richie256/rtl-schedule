import datetime
from unittest.mock import MagicMock, patch
from transit_schedule.mqtt_client import start_mqtt_client

@patch('transit_schedule.mqtt_client.config')
@patch('transit_schedule.mqtt_client.mqtt.Client')
@patch('transit_schedule.mqtt_client.ParseTransitData')
@patch('transit_schedule.mqtt_client.time.sleep')
def test_mqtt_loop_interval_bus_upcoming(mock_sleep, mock_parser, mock_mqtt_client, mock_cfg):
    # Mock config
    mock_cfg.stop_code = "12345"
    mock_cfg.mqtt_host = "localhost"
    mock_cfg.mqtt_port = 1883
    mock_cfg.mqtt_username = None
    mock_cfg.mqtt_password = None
    mock_cfg.mqtt_use_tls = False
    mock_cfg.hass_discovery_enabled = False
    mock_cfg.language = "fr"
    
    # Mock parser
    parser_inst = mock_parser.return_value
    parser_inst.get_stop_id.return_value = "stop_id"
    
    # Mock upcoming bus in 30 seconds
    now = datetime.datetime.now()
    arrival_dt = now + datetime.timedelta(seconds=30)
    
    mock_next_stop = MagicMock()
    mock_next_stop.arrival_datetime = arrival_dt
    mock_next_stop.arrival_time = arrival_dt.strftime("%H:%M:%S")
    mock_next_stop.route_id = "1"
    mock_next_stop.trip_headsign = "Test"
    mock_next_stop.retrieve_method = "GTFS"
    
    parser_inst.get_next_stop.return_value = mock_next_stop
    
    # We want to break the loop after one iteration
    mock_sleep.side_effect = KeyboardInterrupt()
    
    try:
        start_mqtt_client()
    except KeyboardInterrupt:
        pass
    
    # Interval should be 30 + 10 = 40 seconds
    # But it depends on the exact time of 'now' in start_mqtt_client
    # Let's check that it's around 40
    args, _ = mock_sleep.call_args
    interval = args[0]
    assert 35 <= interval <= 45

@patch('transit_schedule.mqtt_client.config')
@patch('transit_schedule.mqtt_client.mqtt.Client')
@patch('transit_schedule.mqtt_client.ParseTransitData')
@patch('transit_schedule.mqtt_client.time.sleep')
def test_mqtt_loop_interval_fallback(mock_sleep, mock_parser, mock_mqtt_client, mock_cfg):
    # Mock config
    mock_cfg.stop_code = "12345"
    mock_cfg.mqtt_host = "localhost"
    mock_cfg.mqtt_port = 1883
    mock_cfg.mqtt_username = None
    mock_cfg.mqtt_password = None
    mock_cfg.mqtt_use_tls = False
    mock_cfg.hass_discovery_enabled = False
    mock_cfg.language = "fr"
    
    # Mock parser
    parser_inst = mock_parser.return_value
    parser_inst.get_stop_id.return_value = "stop_id"
    
    # No bus found
    parser_inst.get_next_stop.return_value = None
    
    # We want to break the loop after one iteration
    mock_sleep.side_effect = KeyboardInterrupt()
    
    try:
        start_mqtt_client()
    except KeyboardInterrupt:
        pass
    
    # Fallback interval should be 120 seconds
    mock_sleep.assert_called_once_with(120)

@patch('transit_schedule.mqtt_client.config')
@patch('transit_schedule.mqtt_client.mqtt.Client')
@patch('transit_schedule.mqtt_client.ParseTransitData')
@patch('transit_schedule.mqtt_client.time.sleep')
def test_mqtt_loop_interval_max_cap(mock_sleep, mock_parser, mock_mqtt_client, mock_cfg):
    # Mock config
    mock_cfg.stop_code = "12345"
    mock_cfg.mqtt_host = "localhost"
    mock_cfg.mqtt_port = 1883
    mock_cfg.mqtt_username = None
    mock_cfg.mqtt_password = None
    mock_cfg.mqtt_use_tls = False
    mock_cfg.hass_discovery_enabled = False
    mock_cfg.language = "fr"
    
    # Mock parser
    parser_inst = mock_parser.return_value
    parser_inst.get_stop_id.return_value = "stop_id"
    
    # Mock upcoming bus in 1 hour
    now = datetime.datetime.now()
    arrival_dt = now + datetime.timedelta(hours=1)
    
    mock_next_stop = MagicMock()
    mock_next_stop.arrival_datetime = arrival_dt
    mock_next_stop.arrival_time = arrival_dt.strftime("%H:%M:%S")
    mock_next_stop.route_id = "1"
    mock_next_stop.trip_headsign = "Test"
    mock_next_stop.retrieve_method = "GTFS"
    
    parser_inst.get_next_stop.return_value = mock_next_stop
    
    # We want to break the loop after one iteration
    mock_sleep.side_effect = KeyboardInterrupt()
    
    try:
        start_mqtt_client()
    except KeyboardInterrupt:
        pass
    
    # Interval should be capped at 120 seconds
    mock_sleep.assert_called_once_with(120)
