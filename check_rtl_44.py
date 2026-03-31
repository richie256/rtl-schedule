
import datetime
import logging
from hastus_scraper import HastusScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtl-schedule")

def check_schedule():
    scraper = HastusScraper()
    stop_id = 2752
    date = datetime.date(2026, 3, 30)
    
    logger.info(f"Checking schedule for stop 32752 on {date}")
    arrivals = scraper.get_schedule(stop_id, date)
    
    if not arrivals:
        logger.warning("No arrivals found.")
        return

    now = datetime.datetime(2026, 3, 30, 20, 26)
    logger.info(f"Current simulated time: {now}")
    
    next_arrivals = [a for a in arrivals if a['arrival_datetime'] > now]
    
    if next_arrivals:
        logger.info(f"Found {len(next_arrivals)} more arrivals today:")
        for a in next_arrivals[:5]:
            logger.info(f" - {a['arrival_time']} {a['trip_headsign']}")
    else:
        logger.info("No more arrivals today. This would trigger look-ahead to tomorrow.")

if __name__ == "__main__":
    check_schedule()
