
import datetime
import pytest
from hastus_scraper import HastusScraper
from const import TARGET_DIRECTION

@pytest.fixture
def scraper():
    """Returns an instance of HastusScraper."""
    return HastusScraper()

def test_rtl_44_schedule_fallback(scraper):
    """
    Test that HastusScraper can correctly fetch and filter schedule 
    for stop 32752 (internal ID 2752) on a specific date, 
    matching the logic in check_rtl_44.py.
    """
    stop_id = 2752
    date = datetime.date(2026, 3, 30)
    
    arrivals = scraper.get_schedule(stop_id, date)
    
    # Assert that we found some arrivals
    assert arrivals, f"No arrivals found for stop {stop_id} on {date}"

    # Replicate the time-based filtering from check_rtl_44.py
    now = datetime.datetime(2026, 3, 30, 20, 26)
    next_arrivals = [a for a in arrivals if a['arrival_datetime'] > now]
    
    # Assert that there are upcoming arrivals for that evening
    assert len(next_arrivals) > 0, f"Expected more arrivals after 20:26 on {date}"
    
    # Basic check on the content of the first upcoming arrival
    first_next = next_arrivals[0]
    assert 'arrival_time' in first_next
    assert 'trip_headsign' in first_next
    if TARGET_DIRECTION:
        assert TARGET_DIRECTION in first_next['trip_headsign']
    assert first_next['arrival_datetime'] > now

def test_hastus_scraper_get_patterns(scraper):
    """Verifies that we can fetch patterns for stop code 32752."""
    stop_code = "32752"
    patterns = scraper.get_stop_patterns(stop_code)
    assert patterns
    # Verify we found the expected route
    if TARGET_DIRECTION:
        assert any(TARGET_DIRECTION in p['ligne'] for p in patterns)

def test_hastus_scraper_cache_logic(scraper):
    """Verifies that caching logic works (integration test)."""
    stop_code = "32752"
    patterns = scraper.get_stop_patterns(stop_code)
    # Find the pattern matching target direction if set
    if TARGET_DIRECTION:
        test_patterns = [p for p in patterns if TARGET_DIRECTION in p['ligne']]
        if not test_patterns:
             pytest.skip(f"Target direction '{TARGET_DIRECTION}' not found in patterns")
        test_pattern = test_patterns[0]
    else:
        test_pattern = patterns[0]
    
    # Monday and Tuesday in the same week should have identical schedules (weekday category)
    mon = datetime.date(2026, 3, 16)
    tue = datetime.date(2026, 3, 17)
    
    mon_schedule = scraper.get_schedule_by_params(test_pattern, mon)
    tue_schedule = scraper.get_schedule_by_params(test_pattern, tue)
    
    assert mon_schedule
    assert tue_schedule
    assert len(mon_schedule) == len(tue_schedule)
    
    # Saturday should likely have a different schedule
    sat = datetime.date(2026, 3, 21)
    sat_schedule = scraper.get_schedule_by_params(test_pattern, sat)
    assert len(sat_schedule) != len(mon_schedule)

def test_hastus_scraper_filtering_logic(scraper):
    """Verifies that get_schedule filters only the target direction."""
    stop_id = 2752
    today = datetime.date(2026, 3, 16)
    
    arrivals = scraper.get_schedule(stop_id, today)
    assert arrivals
    
    # Verify all arrivals contain the target direction if set
    if TARGET_DIRECTION:
        for a in arrivals:
            assert TARGET_DIRECTION in a['trip_headsign']
