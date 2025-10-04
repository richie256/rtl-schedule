
import pytest
from unittest.mock import patch, MagicMock
import datetime
import json

from mqtt_publisher import is_rush_hour, publish_hass_discovery_config

from freezegun import freeze_time

@freeze_time("2023-03-15 07:30:00")
def test_is_rush_hour_morning():
    assert is_rush_hour()

@freeze_time("2023-03-15 16:30:00")
def test_is_rush_hour_evening():
    assert is_rush_hour()

@freeze_time("2023-03-15 12:00:00")
def test_is_not_rush_hour_midday():
    assert not is_rush_hour()

@freeze_time("2023-03-18 08:00:00")
def test_is_not_rush_hour_weekend():
    assert not is_rush_hour()

def test_publish_hass_discovery_config():
    mock_client = MagicMock()
    stop_code = 12345
    discovery_prefix = "homeassistant"

    publish_hass_discovery_config(mock_client, stop_code, discovery_prefix)

    expected_topic = f"{discovery_prefix}/sensor/rtl_schedule_{stop_code}/config"
    
    mock_client.publish.assert_called_once()
    
    args, kwargs = mock_client.publish.call_args
    
    assert args[0] == expected_topic
    assert kwargs['retain'] is True

    payload_dict = json.loads(args[1])
    assert payload_dict['name'] == f"Next Bus at Stop {stop_code}"
    assert payload_dict['unique_id'] == f"rtl_schedule_{stop_code}"
