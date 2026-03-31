import logging
import os

_LOGGER = logging.getLogger("rtl-schedule")


RTL_GTFS_URL = os.environ.get("RTL_GTFS_URL", "http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip")
RTL_GTFS_ZIP_FILE = os.environ.get("RTL_GTFS_ZIP_FILE", "gtfs.zip")
DEFAULT_TIMEZONE = os.environ.get("TZ", "America/Montreal")
RETRIEVAL_METHOD = os.environ.get("RETRIEVAL_METHOD", "live").lower()
LANGUAGE = os.environ.get("LANGUAGE", "fr").lower()

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
