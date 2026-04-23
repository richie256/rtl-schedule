
import os
from unittest.mock import patch
from transit_schedule.config import Config

def test_config_default():
    with patch.dict(os.environ, {}, clear=True):
        cfg = Config()
        assert cfg.transit == "RTL"
        assert cfg.mqtt_port == 1883

def test_config_custom():
    with patch.dict(os.environ, {"TRANSIT": "STM", "MQTT_PORT": "1234"}):
        cfg = Config()
        assert cfg.transit == "STM"
        assert cfg.mqtt_port == 1234

def test_config_invalid_port():
    with patch.dict(os.environ, {"MQTT_PORT": "invalid"}):
        cfg = Config()
        assert cfg.mqtt_port == 1883

def test_config_invalid_stop_code():
    with patch.dict(os.environ, {"STOP_CODE": "invalid"}):
        cfg = Config()
        assert cfg.stop_code is None

def test_config_to_dict():
    cfg = Config()
    d = cfg.to_dict()
    assert isinstance(d, dict)
    assert "transit" in d
    assert all(not k.startswith('_') for k in d.keys())
