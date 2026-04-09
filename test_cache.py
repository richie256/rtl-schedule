import datetime
import pytest
from unittest.mock import MagicMock, patch
from hastus_scraper import HastusScraper

@pytest.fixture
def scraper():
    with patch('hastus_scraper.HastusScraper._initialize'), \
         patch('hastus_scraper.HastusScraper._load_cache'):
        scraper = HastusScraper()
        scraper.buildtime = "20260408"
        return scraper

def test_cache_logic(scraper):
    stop_code = "32752"
    test_pattern = {
        'stop': '2752',
        'pattern': '44_1_1',
        'code': '44',
        'desc': 'Direction Terminus Panama',
        'ligne': '44 Direction Terminus Panama'
    }
    
    # Mock get_stop_patterns to return our test pattern
    scraper.get_stop_patterns = MagicMock(return_value=[test_pattern])
    
    # Mock _get_times_from_cache to return some times
    t1 = datetime.datetime(2026, 3, 16, 8, 0)
    t2 = datetime.datetime(2026, 3, 17, 8, 0)
    
    with patch.object(scraper, 'session') as mock_session:
        # Mock landing page response
        mock_landing_res = MagicMock()
        mock_landing_res.text = '<a href="madOper.php?q=stops_stoptimes&p=2752&s=RTL&web=&pp=44_1_1&l=44&t=regulier">link</a>'
        
        # Mock service period response
        mock_period_res = MagicMock()
        mock_period_res.json.return_value = {
            'data': [
                {'scheduledarrival': 8 * 3600, 'date': '2026-03-16T00:00:00Z'},
                {'scheduledarrival': 8 * 3600, 'date': '2026-03-17T00:00:00Z'},
                {'scheduledarrival': 9 * 3600, 'date': '2026-03-21T00:00:00Z'},
                {'scheduledarrival': 10 * 3600, 'date': '2026-03-22T00:00:00Z'}
            ]
        }
        
        mock_session.get.side_effect = [mock_landing_res, mock_period_res]
        
        # Monday - Should trigger SCRAPE (and cache)
        mon = datetime.date(2026, 3, 16)
        mon_schedule = scraper.get_schedule_by_params(test_pattern, mon)
        assert len(mon_schedule) == 1
        assert mon_schedule[0].time() == datetime.time(8, 0)
        assert mock_session.get.call_count == 2
        
        # Tuesday - Should use CACHE
        tue = datetime.date(2026, 3, 17)
        tue_schedule = scraper.get_schedule_by_params(test_pattern, tue)
        assert len(tue_schedule) == 1
        assert tue_schedule[0].time() == datetime.time(8, 0)
        # Call count should still be 2
        assert mock_session.get.call_count == 2
        
        # Saturday - Should use CACHE
        sat = datetime.date(2026, 3, 21)
        sat_schedule = scraper.get_schedule_by_params(test_pattern, sat)
        assert len(sat_schedule) == 1
        assert sat_schedule[0].time() == datetime.time(9, 0)
        assert mock_session.get.call_count == 2

        # Sunday - Should use CACHE
        sun = datetime.date(2026, 3, 22)
        sun_schedule = scraper.get_schedule_by_params(test_pattern, sun)
        assert len(sun_schedule) == 1
        assert sun_schedule[0].time() == datetime.time(10, 0)
        assert mock_session.get.call_count == 2
