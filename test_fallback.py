import datetime
import logging
import sys
from hastus_scraper import HastusScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtl-schedule")

def main():
    scraper = HastusScraper()
    
    # Internal stop_id for 32752 is 2752
    stop_id = 2752
    today = datetime.date(2026, 3, 16)
    
    logger.info(f"--- Testing get_schedule fallback for stop_id: {stop_id} ---")
    arrivals = scraper.get_schedule(stop_id, today)
    
    if arrivals:
        logger.info(f"SUCCESS: Found {len(arrivals)} arrivals using fallback logic.")
        for a in arrivals[:5]:
            logger.info(f" - {a.strftime('%H:%M')}")
    else:
        logger.error("FAILED: No arrivals found using fallback logic.")

if __name__ == "__main__":
    main()
