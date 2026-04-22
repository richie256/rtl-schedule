
import logging
import os
from typing import Any

_LOGGER = logging.getLogger("transit-schedule")

class Config:
    def __init__(self):
        # Transit Configuration
        self.transit = os.environ.get("TRANSIT", "RTL").upper()
        
        # GTFS Configuration
        default_urls = {
            "RTL": "http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip",
            "STM": "https://www.stm.info/sites/default/files/gtfs/gtfs_stm.zip",
            "STL": "https://www.stlaval.ca/datas/opendata/GTF_STL.zip"
        }
        self.gtfs_url = os.environ.get("GTFS_URL", default_urls.get(self.transit, default_urls["RTL"]))
        self.gtfs_zip_file = os.environ.get("GTFS_ZIP_FILE", f"gtfs_{self.transit.lower()}.zip")
        self.gtfs_data_dir = os.environ.get("GTFS_DATA_DIR", "data")
        self.retrieval_method = os.environ.get("RETRIEVAL_METHOD", "gtfs" if self.transit != "RTL" else "live").lower()
        self.timezone = os.environ.get("TZ", "America/Montreal")
        self.language = os.environ.get("LANGUAGE", "fr").lower()
        
        # Filtering Configuration
        default_directions = {
            "RTL": "Direction Terminus Panama",
            "STM": "",
            "STL": ""
        }
        self.target_direction = os.environ.get("TARGET_DIRECTION", default_directions.get(self.transit, ""))
        self.target_route = os.environ.get("TARGET_ROUTE")
        self.force_cache_refresh = os.environ.get("FORCE_CACHE_REFRESH", "False").lower() == "true"

        # MQTT Configuration
        self.mqtt_host = os.environ.get("MQTT_HOST")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", 1883))
        self.mqtt_username = os.environ.get("MQTT_USERNAME")
        self.mqtt_password = os.environ.get("MQTT_PASSWORD")
        self.mqtt_use_tls = os.environ.get("MQTT_USE_TLS", "False").lower() == "true"
        
        # Stop Configuration
        try:
            self.stop_code = int(os.environ["STOP_CODE"]) if "STOP_CODE" in os.environ else None
        except ValueError:
            _LOGGER.error("STOP_CODE must be an integer")
            self.stop_code = None

        # Home Assistant Discovery
        self.hass_discovery_enabled = os.environ.get("HASS_DISCOVERY_ENABLED", "False").lower() == "true"
        self.hass_discovery_prefix = os.environ.get("HASS_DISCOVERY_PREFIX", "homeassistant")

        # MQTT Topics
        self.mqtt_refresh_topic = os.environ.get("MQTT_REFRESH_TOPIC", f"{self.transit.lower()}/schedule/refresh")
        self.mqtt_state_topic = os.environ.get("MQTT_STATE_TOPIC", f"home/transit/{self.transit.lower()}/stop_{self.stop_code}" if self.stop_code else f"home/transit/{self.transit.lower()}/stop_unknown")
        self.mqtt_hass_status_topic = os.environ.get("MQTT_HASS_STATUS_TOPIC", f"{self.hass_discovery_prefix}/status")

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

# Global config instance
config = Config()
