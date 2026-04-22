
import datetime
import json
from unittest.mock import MagicMock

import pytest

from transit_schedule.const import TARGET_DIRECTION
from transit_schedule.hastus_scraper import HastusScraper


def test_hastus_scraper_route_filtering(scraper, mocker):
    """Verifies that get_schedule filters by TARGET_ROUTE."""
    stop_id = 2752
    today = datetime.date(2026, 3, 16)
    
    # Mock patterns: one 44, one 47
    patterns = [
        {"stop": "2752", "pattern": "P1", "ligne": " 44 Direction Terminus Panama"},
        {"stop": "2752", "pattern": "P2", "ligne": " 47 Direction Terminus Panama"}
    ]
    mocker.patch.object(scraper, 'get_stop_patterns', return_value=patterns)
    mocker.patch.object(scraper, 'get_schedule_by_params', return_value=[datetime.datetime.combine(today, datetime.time(10, 0))])
    
    # Mock TARGET_ROUTE to "44"
    mocker.patch('transit_schedule.hastus_scraper.TARGET_ROUTE', "44")
    
    arrivals = scraper.get_schedule(stop_id, today)
    assert arrivals
    assert all(a['route_id'] == "44" for a in arrivals)
    assert len(arrivals) == 1

def test_parse_json_weekly_schedule_robust_matching(scraper):
    """Verifies that _parse_json_weekly_schedule doesn't confuse similar IDs (e.g. 44 and 144)."""
    json_data = {
        'data': [
            {'scheduledarrival': 28800, 'date': '2026-03-16T00:00:00Z', 'stopid': 'S1', 'id': '15:44:1:01'},
            {'scheduledarrival': 32400, 'date': '2026-03-16T00:00:00Z', 'stopid': 'S1', 'id': '15:144:1:01'}
        ]
    }
    target_date = datetime.date(2026, 3, 16)
    
    # Searching for '44' should NOT find '144'
    data_44 = scraper._parse_json_weekly_schedule(json_data, 'S1', '44', target_date)
    assert len(data_44['semaine']) == 1
    assert data_44['semaine'][0] == datetime.time(8, 0)
    
    # Searching for '144' should NOT find '44'
    data_144 = scraper._parse_json_weekly_schedule(json_data, 'S1', '144', target_date)
    assert len(data_144['semaine']) == 1
    assert data_144['semaine'][0] == datetime.time(9, 0)


def test_hastus_scraper_late_night_times(scraper):
    """Verifies that times like 24:30 are correctly projected to the next day, especially across category changes."""
    json_data = {
        'data': [
            {'scheduledarrival': 88200, 'date': '2026-04-24T00:00:00Z', 'stopid': 'S1', 'id': 'P1:01'}, # Fri 24:30
        ]
    }
    target_date = datetime.date(2026, 4, 24) # Friday
    
    # Current implementation would put 00:30 in Friday's category (semaine)
    data = scraper._parse_json_weekly_schedule(json_data, 'S1', 'P1', target_date)
    
    # Setup cache with this data
    # Note: 'samedi' and 'dimanche' are empty
    cache_key = ("S1", "P1", datetime.date(2026, 4, 20))
    scraper.schedule_cache[cache_key] = data
    
    # Search on Friday at 23:50
    arrivals = scraper._get_times_from_cache(data, target_date)
    
    # The arrival should be Saturday 00:30
    # If the bug exists, this will FAIL because samedi category is empty
    assert any(a == datetime.datetime(2026, 4, 25, 0, 30) for a in arrivals)

def test_parse_html_weekly_schedule_late_night(scraper):
    """Verifies that HTML parser handles 24:30+."""
    html = """
    <table>
        <tr><td><b>Semaine</b></td></tr>
        <tr><td>24:30</td></tr>
    </table>
    """
    data = scraper._parse_html_weekly_schedule(html)
    assert datetime.time(0, 30) in data['semaine']

def test_hastus_scraper_ignore_irrelevant_links(scraper, mocker):
    """Verifies that links from previous/future weeks are ignored."""
    test_pattern = {"stop": "2752", "pattern": "P1", "ligne": "44"}
    search_date = datetime.date(2026, 4, 22) # Wednesday
    
    # Mock landing page with one valid link and one from a past week
    mock_landing = MagicMock()
    mock_landing.text = """
        <a href="madOper.php?q=stops_stoptimes&t=20260422">Current Wed</a>
        <a href="madOper.php?q=stops_stoptimes&t=20260412">Past Sunday</a>
    """
    
    # Mock JSON response only for the valid link
    mock_json = {'data': [{'scheduledarrival': 36000, 'stopid': '2752', 'id': 'P1:01'}]}
    
    def side_effect(url, **kwargs):
        mock_res = MagicMock()
        if "t=20260422" in url:
            mock_res.json.return_value = mock_json
            mock_res.text = json.dumps(mock_json)
        elif "t=20260412" in url:
            pytest.fail("Should NOT fetch historical link")
        else:
            mock_res = mock_landing
            mock_res.text = mock_landing.text
        return mock_res

    mocker.patch.object(scraper.session, 'get', side_effect=side_effect)
    
    cache_key = ("2752", "P1", datetime.date(2026, 4, 20))
    scraper._fetch_and_cache(test_pattern, search_date, cache_key)
    
    # Verify only current week data is in cache
    assert len(scraper.schedule_cache[cache_key]['semaine']) == 1
    assert len(scraper.schedule_cache[cache_key]['dimanche']) == 0
    """Verifies that links for different days are correctly categorized during cache population."""
    test_pattern = {"stop": "2752", "pattern": "P1", "ligne": "44"}
    search_date = datetime.date(2026, 4, 22) # Wednesday
    
    # Mock landing page with two links: one weekday, one Saturday
    mock_landing = MagicMock()
    mock_landing.text = """
        <a href="madOper.php?q=stops_stoptimes&t=20260422">Semaine</a>
        <a href="madOper.php?q=stops_stoptimes&t=20260425">Samedi</a>
    """
    
    # Mock JSON responses for both links
    mock_json_weekday = {
        'data': [{'scheduledarrival': 36000, 'stopid': '2752', 'id': 'P1:01'}] # 10:00
    }
    mock_json_sat = {
        'data': [{'scheduledarrival': 39600, 'stopid': '2752', 'id': 'P1:01'}] # 11:00
    }
    
    def side_effect(url, **kwargs):
        mock_res = MagicMock()
        if "t=20260422" in url:
            mock_res.json.return_value = mock_json_weekday
            mock_res.text = json.dumps(mock_json_weekday)
        elif "t=20260425" in url:
            mock_res.json.return_value = mock_json_sat
            mock_res.text = json.dumps(mock_json_sat)
        else:
            mock_res = mock_landing
            mock_res.text = mock_landing.text
        return mock_res

    mocker.patch.object(scraper.session, 'get', side_effect=side_effect)
    
    cache_key = ("2752", "P1", datetime.date(2026, 4, 20))
    scraper._fetch_and_cache(test_pattern, search_date, cache_key)
    
    cached_data = scraper.schedule_cache[cache_key]
    
    # Weekday category should only have the 10:00 time
    assert datetime.time(10, 0) in cached_data['semaine']
    assert datetime.time(11, 0) not in cached_data['semaine']
    
    # Saturday category should only have the 11:00 time
    assert datetime.time(11, 0) in cached_data['samedi']
    assert datetime.time(10, 0) not in cached_data['samedi']


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

def test_parse_html_weekly_schedule(scraper):
    html = """
    <table>
        <tr><td><b>Semaine</b></td></tr>
        <tr><td>08:00</td></tr>
        <tr><td>25:15</td></tr>
    </table>
    <table>
        <tr><td><b>Samedi</b></td></tr>
        <tr><td>09:00</td></tr>
    </table>
    <table>
        <tr><td><b>Dimanche</b></td></tr>
        <tr><td>10:00</td></tr>
    </table>
    """
    data = scraper._parse_html_weekly_schedule(html)
    assert len(data['semaine']) == 2
    assert data['semaine'][0] == datetime.time(1, 15) # 25:15 % 24
    assert data['semaine'][1] == datetime.time(8, 0)
    
    # 25:15 from semaine also goes into samedi
    assert len(data['samedi']) == 2
    assert data['samedi'][0] == datetime.time(1, 15)
    assert data['samedi'][1] == datetime.time(9, 0)
    
    assert data['dimanche'][0] == datetime.time(10, 0)

def test_get_stop_code_from_id(scraper):
    scraper.stop_mappings = {"32752": ["15:2752"], "12345": ["15:6789"]}
    assert scraper.get_stop_code_from_id(2752) == "32752"
    assert scraper.get_stop_code_from_id(6789) == "12345"
    assert scraper.get_stop_code_from_id(9999) is None

def test_load_save_cache(scraper, mocker):
    mocker.patch("os.path.exists", return_value=True)
    cache_data = {
        "version": "2",
        "data": {
            "2752|P1|2026-03-16": {
                "semaine": ["08:00:00"],
                "samedi": [],
                "dimanche": []
            }
        }
    }
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(cache_data)))
    
    scraper._load_cache()
    key = ("2752", "P1", datetime.date(2026, 3, 16))
    assert key in scraper.schedule_cache
    assert scraper.schedule_cache[key]['semaine'][0] == datetime.time(8, 0)

    # Test save
    mock_open = mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("os.makedirs")
    scraper._save_cache()
    assert mock_open.called

def test_initialize_error(scraper, mocker):
    mock_res = MagicMock()
    mock_res.raise_for_status.side_effect = Exception("Network Error")
    mocker.patch.object(scraper.session, 'get', return_value=mock_res)
    
    scraper.buildtime = None
    scraper._initialize()
    assert scraper.buildtime is None
