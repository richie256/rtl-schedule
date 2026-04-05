
import datetime
import pytest
from unittest.mock import patch, MagicMock
from hastus_scraper import HastusScraper
from const import TARGET_DIRECTION

@pytest.fixture
def scraper(mocker):
    """Returns an instance of HastusScraper with basic network calls mocked."""
    # Prevent __init__ from hitting the network
    mocker.patch.object(HastusScraper, '_initialize', return_value=None)
    mocker.patch.object(HastusScraper, 'fetch_stop_mappings', return_value=None)
    
    s = HastusScraper()
    s.stop_mappings = {"32752": ["15:2752"]}
    return s

def test_rtl_44_schedule_fallback(scraper, mocker):
    """
    Test that HastusScraper can correctly fetch and filter schedule 
    for stop 32752 (internal ID 2752) on a specific date.
    """
    stop_id = 2752
    date = datetime.date(2026, 3, 30)
    
    # Mock get_stop_patterns
    patterns = [{
        "stop": "2752",
        "pattern": "P1",
        "code": "C1",
        "desc": "D1",
        "ligne": " 44 Direction Terminus Panama"
    }]
    mocker.patch.object(scraper, 'get_stop_patterns', return_value=patterns)
    
    # Mock get_schedule_by_params
    arrival_time = datetime.datetime(2026, 3, 30, 21, 0, 0)
    mocker.patch.object(scraper, 'get_schedule_by_params', return_value=[arrival_time])
    
    arrivals = scraper.get_schedule(stop_id, date)
    
    # Assert that we found some arrivals
    assert arrivals, f"No arrivals found for stop {stop_id} on {date}"

    # Replicate the time-based filtering from check_rtl_44.py
    now = datetime.datetime(2026, 3, 30, 20, 26)
    next_arrivals = [a for a in arrivals if a['arrival_datetime'] > now]
    
    assert len(next_arrivals) > 0
    first_next = next_arrivals[0]
    if TARGET_DIRECTION:
        assert TARGET_DIRECTION in first_next['trip_headsign']
    assert first_next['arrival_datetime'] > now

def test_hastus_scraper_get_patterns(scraper, mocker):
    """Verifies that we can fetch patterns for stop code 32752."""
    stop_code = "32752"
    
    # Mock the session response for patterns
    mock_res = MagicMock()
    mock_res.text = "urlHoraireArret('2752','P1','C1','D1',' 44 Direction Terminus Panama');"
    mocker.patch.object(scraper.session, 'get', return_value=mock_res)
    
    patterns = scraper.get_stop_patterns(stop_code)
    assert patterns
    assert patterns[0]['ligne'] == " 44 Direction Terminus Panama"

def test_hastus_scraper_cache_logic(scraper, mocker):
    """Verifies that caching logic works with mocks."""
    test_pattern = {
        "stop": "2752",
        "pattern": "P1",
        "ligne": " 44 Direction Terminus Panama"
    }
    
    # Setup mock weekly data
    weekday_time = datetime.time(10, 0)
    sat_time = datetime.time(11, 0)
    
    weekly_data = {
        'semaine': [weekday_time],
        'samedi': [sat_time],
        'dimanche': []
    }
    
    # Populate the cache directly to test _get_times_from_cache through get_schedule_by_params indirectly
    # or just mock the network call that populates it.
    
    # Mock the landing page and service period link calls
    mocker.patch.object(scraper, 'session')
    
    # For simplicity, let's mock the schedule_cache directly or the method that returns it
    cache_key = (test_pattern['stop'], test_pattern['pattern'], datetime.date(2026, 3, 16))
    scraper.schedule_cache[cache_key] = weekly_data
    
    # Monday and Tuesday in the same week should have identical schedules
    mon = datetime.date(2026, 3, 16)
    tue = datetime.date(2026, 3, 17)
    
    mon_schedule = scraper.get_schedule_by_params(test_pattern, mon)
    tue_schedule = scraper.get_schedule_by_params(test_pattern, tue)
    
    assert len(mon_schedule) == 1
    assert mon_schedule[0].time() == weekday_time
    assert len(tue_schedule) == 1
    assert tue_schedule[0].time() == mon_schedule[0].time()
    assert mon_schedule[0].date() != tue_schedule[0].date()
    
    # Saturday
    sat = datetime.date(2026, 3, 21)
    sat_schedule = scraper.get_schedule_by_params(test_pattern, sat)
    assert len(sat_schedule) == 1
    assert sat_schedule[0].time() == sat_time

def test_hastus_scraper_filtering_logic(scraper, mocker):
    """Verifies that get_schedule filters only the target direction."""
    stop_id = 2752
    today = datetime.date(2026, 3, 16)
    
    # Mock patterns: one Panama, one not
    patterns = [
        {"stop": "2752", "pattern": "P1", "ligne": " 44 Direction Terminus Panama"},
        {"stop": "2752", "pattern": "P2", "ligne": " 44 Direction Somewhere Else"}
    ]
    mocker.patch.object(scraper, 'get_stop_patterns', return_value=patterns)
    mocker.patch.object(scraper, 'get_schedule_by_params', return_value=[datetime.datetime.combine(today, datetime.time(10, 0))])
    
    arrivals = scraper.get_schedule(stop_id, today)
    assert arrivals
    
    if TARGET_DIRECTION:
        for a in arrivals:
            assert TARGET_DIRECTION in a['trip_headsign']
        # Should only have arrivals for Panama
        assert all("Terminus Panama" in a['trip_headsign'] for a in arrivals)
