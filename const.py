import logging
from config import config

_LOGGER = logging.getLogger("rtl-schedule")

RTL_GTFS_URL = config.rtl_gtfs_url
RTL_GTFS_ZIP_FILE = config.rtl_gtfs_zip_file
DEFAULT_TIMEZONE = config.timezone
RETRIEVAL_METHOD = config.retrieval_method
LANGUAGE = config.language
TARGET_DIRECTION = config.target_direction

TRANSLATIONS = {
    "en": {
        "next_bus_at_stop": "Next Bus at Stop {stop_code}",
        "rtl_schedule": "RTL Schedule",
        "gtfs": "GTFS",
        "live_scraper": "Live Scraper",
        "no_more_buses": "No more buses for today.",
        "refresh_action_received": "Refresh action received",
        "refresh_period_ended": "Refresh period ended",
        "waiting_for": "Waiting for {interval} seconds...",
    },
    "fr": {
        "next_bus_at_stop": "Prochain bus à l'arrêt {stop_code}",
        "rtl_schedule": "Horaire RTL",
        "gtfs": "GTFS",
        "live_scraper": "Scraper en direct",
        "no_more_buses": "Plus de bus pour aujourd'hui.",
        "refresh_action_received": "Action de rafraîchissement reçue",
        "refresh_period_ended": "Période de rafraîchissement terminée",
        "waiting_for": "Attente de {interval} secondes...",
    }
}
