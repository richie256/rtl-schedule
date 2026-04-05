import pytest
from unittest.mock import patch, MagicMock
import os
import datetime
import pandas as pd
from zipfile import ZipFile

from data_parser import ParseRTLData
from const import RTL_GTFS_ZIP_FILE, TARGET_DIRECTION

@pytest.fixture
def gtfs_zip_file():
    # Create a dummy gtfs.zip file for testing
    with ZipFile(RTL_GTFS_ZIP_FILE, 'w') as zf:
        stops_data = 'stop_id,stop_code,stop_name\n1,123,Test Stop 1\n2,456,Test Stop 2'
        zf.writestr('stops.txt', stops_data)

        # Service for today (Monday) and tomorrow (Tuesday)
        calendar_data = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231'
        zf.writestr('calendar.txt', calendar_data)

        # Arrivals at 10:00 AM and 06:00 AM next day
        stop_times_data = 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1\n2,06:00:00,06:00:30,1,1'
        zf.writestr('stop_times.txt', stop_times_data)

        headsign = TARGET_DIRECTION if TARGET_DIRECTION else "Direction Terminus Panama"
        trips_data = f'route_id,service_id,trip_id,trip_headsign\n101,1,1,{headsign}\n101,1,2,{headsign}'
        zf.writestr('trips.txt', trips_data)
    yield
    if os.path.exists(RTL_GTFS_ZIP_FILE):
        os.remove(RTL_GTFS_ZIP_FILE)

@patch('data_parser.RETRIEVAL_METHOD', 'gtfs')
@patch('data_parser.HastusScraper')
@patch('data_parser.is_file_expired', return_value=False)
def test_get_next_stop_lookahead(mock_is_file_expired, mock_hastus_scraper, gtfs_zip_file):
    parser = ParseRTLData()
    
    # Monday at 23:45 PM - Should find nothing for today, and look at Tuesday 06:00 AM
    test_datetime = datetime.datetime(2025, 9, 29, 23, 45, 0)
    
    # Mock scraper to return nothing so we test GTFS lookahead
    mock_hastus_scraper.return_value.get_schedule.return_value = []
    
    next_stop = parser.get_next_stop(1, test_datetime)
    
    assert next_stop is not None
    # Should be the 06:00 AM bus
    assert next_stop.arrival_time == '06:00:00'
    # Date should be Tuesday (30th)
    assert next_stop.arrival_datetime.date() == datetime.date(2025, 9, 30)
    assert next_stop.retrieve_method == 'GTFS'

@patch('data_parser.RETRIEVAL_METHOD', 'gtfs')
@patch('data_parser.HastusScraper')
@patch('data_parser.is_file_expired', return_value=False)
def test_get_next_stop(mock_is_file_expired, mock_hastus_scraper, gtfs_zip_file):
    parser = ParseRTLData()
    # Monday at 09:00 AM
    test_datetime = datetime.datetime(2025, 9, 29, 9, 0, 0)
    next_stop = parser.get_next_stop(1, test_datetime)
    assert next_stop is not None
    assert next_stop.route_id == 101
    assert next_stop.arrival_time == '10:00:00'
    assert next_stop.retrieve_method == 'GTFS'

@patch('data_parser.RETRIEVAL_METHOD', 'live')
@patch('data_parser.HastusScraper')
@patch('data_parser.is_file_expired', return_value=False)
@patch('os.path.isfile', return_value=True)
@patch('data_parser.read_csv')
@patch('zipfile.ZipFile')
def test_get_next_stop_live_mode(mock_zipfile, mock_read_csv, mock_isfile, mock_is_file_expired, mock_hastus_scraper):
    """Verifies that in 'live' mode, it uses HastusScraper and skips GTFS."""
    # Mock dataframes to avoid initialization errors
    mock_read_csv.return_value = MagicMock()
    
    mock_scraper_inst = mock_hastus_scraper.return_value
    mock_scraper_inst.get_schedule.return_value = [
        {
            'arrival_datetime': datetime.datetime(2025, 9, 29, 10, 0, 0),
            'arrival_time': '10:00:00',
            'route_id': '44',
            'trip_headsign': '44 Direction Terminus Panama'
        }
    ]
    
    parser = ParseRTLData()
    test_datetime = datetime.datetime(2025, 9, 29, 9, 0, 0)
    next_stop = parser.get_next_stop(2752, test_datetime)
    
    assert next_stop is not None
    assert next_stop.retrieve_method == 'live scraper'
    assert next_stop.route_id == '44'
    mock_scraper_inst.get_schedule.assert_called_once()
