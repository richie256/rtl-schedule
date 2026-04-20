from unittest.mock import MagicMock, patch


class MockConfig:
    def __init__(self):
        self.stop_code = 12345
        self.mqtt_host = "localhost"
        self.mqtt_port = 1883
        self.mqtt_username = None
        self.mqtt_password = None
        self.mqtt_use_tls = False
        self.mqtt_refresh_topic = "rtl/schedule/refresh"
        self.mqtt_hass_status_topic = "homeassistant/status"
        self.hass_discovery_enabled = True
        self.hass_discovery_prefix = "homeassistant"
        self.language = "en"
        self.mqtt_state_topic = "topic"

    def to_dict(self):
        return {}

@patch('transit_schedule.mqtt_client.config')
@patch('transit_schedule.mqtt_client.mqtt.Client')
@patch('transit_schedule.mqtt_client.ParseTransitData')
@patch('transit_schedule.mqtt_client.publish_schedule')
@patch('transit_schedule.mqtt_client.publish_hass_discovery_config')
@patch('transit_schedule.mqtt_client.time.sleep', side_effect=KeyboardInterrupt)
def test_on_message_hass_status(mock_sleep, mock_publish_discovery, mock_publish_schedule, mock_rtl_parser, mock_mqtt_client, mock_cfg):
    # Setup mock config
    cfg = MockConfig()
    mock_cfg.__dict__.update(cfg.__dict__)
    mock_cfg.mqtt_refresh_topic = cfg.mqtt_refresh_topic
    mock_cfg.mqtt_hass_status_topic = cfg.mqtt_hass_status_topic
    mock_cfg.hass_discovery_enabled = cfg.hass_discovery_enabled
    mock_cfg.hass_discovery_prefix = cfg.hass_discovery_prefix
    mock_cfg.stop_code = cfg.stop_code

    mock_parser_inst = mock_rtl_parser.return_value
    mock_parser_inst.get_stop_id.return_value = "stop_id_123"

    # Capture the on_message callback
    client_inst = mock_mqtt_client.return_value
    
    # Run start_mqtt_client in a way that we can trigger the callback
    from transit_schedule.mqtt_client import start_mqtt_client
    
    # We need to reach the point where on_message is assigned
    # but we can't easily run the loop. 
    # Let's mock the loop to just run once or something.
    
    on_message_callback = None
    def mock_set_on_message(cb):
        nonlocal on_message_callback
        on_message_callback = cb
    client_inst.on_message = None # This is a property in real paho, but here it's a mock

    # Re-mock start_mqtt_client's use of client
    with patch('transit_schedule.mqtt_client.mqtt.Client') as mock_mqtt_client:
        client_inst = mock_mqtt_client.return_value
        
        # We need to simulate the execution of start_mqtt_client up to loop_start
        # and then call the callback it registered.
        
        # To do this without running the infinite loop, we can mock time.sleep to raise an exception
        # after we've had a chance to call the callback.
        
        def run_then_break(*args, **kwargs):
            # This is called by time.sleep(interval)
            # Before breaking, we simulate receiving a message
            msg = MagicMock()
            msg.topic = "homeassistant/status"
            msg.payload = b"online"
            
            # The on_message callback is defined inside start_mqtt_client
            # It's assigned to client.on_message
            client_inst.on_message(client_inst, None, msg)
            raise KeyboardInterrupt

        mock_sleep.side_effect = run_then_break
        
        try:
            start_mqtt_client()
        except KeyboardInterrupt:
            pass

        # Verify that discovery config was published (once at start, once on HA status)
        assert mock_publish_discovery.call_count == 2
        # Verify schedule was published
        assert mock_publish_schedule.called
