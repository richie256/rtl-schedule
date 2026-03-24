import datetime
import logging
import sys
from hastus_scraper import HastusScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtl-schedule")

def main():
    scraper = HastusScraper()
    
    # Test stop code
    stop_code = "32752"
    logger.info(f"Fetching patterns for stop code: {stop_code}")
    
    patterns = scraper.get_stop_patterns(stop_code)
    if not patterns:
        logger.error(f"No patterns found for stop {stop_code}")
        return

    logger.info(f"Found {len(patterns)} patterns for stop {stop_code}:")
    for idx, p in enumerate(patterns):
        logger.info(f"[{idx}] {p['ligne']} (Pattern: {p['pattern']}, Internal Stop: {p['stop']})")

    # Fetch schedule for the first pattern found
    test_pattern = patterns[0]
    today = datetime.date(2026, 3, 16) # Using the date from user's example
    
    logger.info(f"Fetching schedule for pattern: {test_pattern['ligne']} on {today}")
    schedule = scraper.get_schedule_by_params(test_pattern, today)
    
    logger.info(f"Fetched {len(schedule)} arrival times.")
    for arrival in schedule[:10]:
        logger.info(f" - {arrival.strftime('%H:%M')}")
    if len(schedule) > 10:
        logger.info(" ...")

if __name__ == "__main__":
    main()
