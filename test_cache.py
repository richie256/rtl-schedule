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
    patterns = scraper.get_stop_patterns(stop_code)
    if not patterns:
        logger.error(f"No patterns found for stop {stop_code}")
        return

    test_pattern = patterns[0] # 44 Direction Terminus Panama
    
    # Monday
    mon = datetime.date(2026, 3, 16)
    logger.info("--- Fetching Monday (Should trigger SCRAPE) ---")
    mon_schedule = scraper.get_schedule_by_params(test_pattern, mon)
    logger.info(f"Monday count: {len(mon_schedule)}")
    
    # Tuesday (Same week)
    tue = datetime.date(2026, 3, 17)
    logger.info("--- Fetching Tuesday (Should use CACHE) ---")
    tue_schedule = scraper.get_schedule_by_params(test_pattern, tue)
    logger.info(f"Tuesday count: {len(tue_schedule)}")
    
    # Saturday (Same week)
    sat = datetime.date(2026, 3, 21)
    logger.info("--- Fetching Saturday (Should use CACHE) ---")
    sat_schedule = scraper.get_schedule_by_params(test_pattern, sat)
    logger.info(f"Saturday count: {len(sat_schedule)}")

    # Sunday (Same week)
    sun = datetime.date(2026, 3, 22)
    logger.info("--- Fetching Sunday (Should use CACHE) ---")
    sun_schedule = scraper.get_schedule_by_params(test_pattern, sun)
    logger.info(f"Sunday count: {len(sun_schedule)}")

    # Check if Mon and Tue are same (they use the 'semaine' category)
    if len(mon_schedule) == len(tue_schedule):
        logger.info("SUCCESS: Monday and Tuesday have same number of arrivals (cached 'semaine')")
    
    # Check if Sat is different
    if len(sat_schedule) != len(mon_schedule):
        logger.info(f"SUCCESS: Saturday has different number of arrivals ({len(sat_schedule)} vs {len(mon_schedule)})")

if __name__ == "__main__":
    main()
