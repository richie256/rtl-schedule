import datetime
import os
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pandas as pd
import pytest

from transit_schedule.const import GTFS_ZIP_FILE, TARGET_DIRECTION
from transit_schedule.data_parser import ParseTransitData


@pytest.fixture
def gtfs_zip_file():
    # Create a dummy gtfs.zip file for testing
    with ZipFile(GTFS_ZIP_FILE, 'w') as zf:
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
    if os.path.exists(GTFS_ZIP_FILE):
        os.remove(GTFS_ZIP_FILE)

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.HastusScraper')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_get_next_stop_lookahead(mock_is_file_expired, mock_hastus_scraper, mock_config, gtfs_zip_file):
    mock_config.retrieval_method = 'gtfs'
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    mock_config.transit = 'RTL'
    parser = ParseTransitData()
    
    # Monday at 23:45 PM - Should find nothing for today, and look at Tuesday 06:00 AM
    test_datetime = datetime.datetime(2025, 9, 29, 23, 45, 0)
    
    # Mock scraper to return nothing so we test GTFS lookahead
    mock_hastus_scraper.return_value.get_schedule.return_value = []
    
    next_stop = parser.get_next_stop('1', test_datetime)
    
    assert next_stop is not None
    # Should be the 06:00 AM bus
    assert next_stop.arrival_time == '06:00:00'
    # Date should be Tuesday (30th)
    assert next_stop.arrival_datetime.date() == datetime.date(2025, 9, 30)
    assert next_stop.retrieve_method == 'GTFS'

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.HastusScraper')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_get_next_stop(mock_is_file_expired, mock_hastus_scraper, mock_config, gtfs_zip_file):
    mock_config.retrieval_method = 'gtfs'
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    mock_config.transit = 'RTL'
    parser = ParseTransitData()
    # Monday at 09:00 AM
    test_datetime = datetime.datetime(2025, 9, 29, 9, 0, 0)
    next_stop = parser.get_next_stop('1', test_datetime)
    assert next_stop is not None
    assert next_stop.route_id == '101'
    assert next_stop.arrival_time == '10:00:00'
    assert next_stop.retrieve_method == 'GTFS'

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.HastusScraper')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
@patch('os.path.isfile', return_value=True)
@patch('transit_schedule.data_parser.read_csv')
@patch('transit_schedule.data_parser.zipfile.ZipFile')
def test_get_next_stop_live_mode(mock_zipfile, mock_read_csv, mock_isfile, mock_is_file_expired, mock_hastus_scraper, mock_config):
    """Verifies that in 'live' mode, it uses HastusScraper and skips GTFS."""
    mock_config.retrieval_method = 'live'
    mock_config.transit = 'RTL'
    mock_config.gtfs_data_dir = '.'
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
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
    
    parser = ParseTransitData()
    test_datetime = datetime.datetime(2025, 9, 29, 9, 0, 0)
    next_stop = parser.get_next_stop('2752', test_datetime)
    
    assert next_stop is not None
    assert next_stop.retrieve_method == 'live scraper'
    assert next_stop.route_id == '44'
    mock_scraper_inst.get_schedule.assert_called_once()

def test_load_data_file_not_found(mocker):
    mocker.patch('os.path.isfile', return_value=False)
    mocker.patch('transit_schedule.data_parser.is_file_expired', return_value=False)
    mocker.patch('transit_schedule.data_parser.ParseTransitData._download_gtfs_file', side_effect=FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        ParseTransitData()

def test_load_data_bad_zip(mocker):
    mocker.patch('os.path.isfile', return_value=True)
    mocker.patch('transit_schedule.data_parser.is_file_expired', return_value=False)
    from zipfile import BadZipFile
    mocker.patch('transit_schedule.data_parser.zipfile.ZipFile', side_effect=BadZipFile)
    with pytest.raises(BadZipFile):
        ParseTransitData()

@patch('transit_schedule.data_parser.requests.get')
def test_download_gtfs_file(mock_get, mocker):
    mock_res = MagicMock()
    mock_res.content = b'fake zip content'
    mock_get.return_value = mock_res
    
    mocker.patch('builtins.open', mocker.mock_open())
    ParseTransitData._download_gtfs_file('fake_path.zip')
    mock_get.assert_called_once()

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_get_stop_id_not_found(mock_is_file_expired, mock_config, gtfs_zip_file):
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    parser = ParseTransitData()
    assert parser.get_stop_id(999) is None

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_get_service_id_with_exceptions(mock_is_file_expired, mock_config, mocker):
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    # Setup GTFS with calendar_dates.txt
    with ZipFile(GTFS_ZIP_FILE, 'w') as zf:
        zf.writestr('stops.txt', 'stop_id,stop_code\n1,123')
        zf.writestr('calendar.txt', 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231')
        zf.writestr('stop_times.txt', 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1')
        zf.writestr('trips.txt', 'route_id,service_id,trip_id,trip_headsign\n101,1,1,Panama')
        # Add a date exception: remove service 1 on a Monday (2025-09-29)
        zf.writestr('calendar_dates.txt', 'service_id,date,exception_type\n1,20250929,2\n2,20250929,1')
    
    parser = ParseTransitData()
    # 2025-09-29 is Monday. Regular service 1 is removed, service 2 is added.
    service_ids = parser._get_service_ids(datetime.date(2025, 9, 29))
    assert '2' in service_ids
    assert '1' not in service_ids
    
    if os.path.exists(GTFS_ZIP_FILE):
        os.remove(GTFS_ZIP_FILE)

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_calculate_arrival_datetimes_midnight(mock_is_file_expired, mock_config, gtfs_zip_file):
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    parser = ParseTransitData()
    df = pd.DataFrame({
        'arrival_time': ['24:15:00', '08:00:00'],
        'trip_id': ['1', '2']
    })
    date = datetime.date(2025, 9, 29)
    result = parser._calculate_arrival_datetimes(df, date)
    # 08:00:00 today comes first
    assert result.iloc[0]['arrival_datetime'] == datetime.datetime(2025, 9, 29, 8, 0, 0)
    # 24:15:00 becomes 00:15:00 next day (tomorrow)
    assert result.iloc[1]['arrival_datetime'] == datetime.datetime(2025, 9, 30, 0, 15, 0)

@patch('transit_schedule.data_parser.config')
@patch('transit_schedule.data_parser.is_file_expired', return_value=False)
def test_get_stop_date_range(mock_is_file_expired, mock_config, gtfs_zip_file):
    mock_config.gtfs_zip_file = GTFS_ZIP_FILE
    mock_config.gtfs_data_dir = '.'
    parser = ParseTransitData()
    min_d, max_d = parser._get_stop_date_range('1')
    assert min_d == 20250101
    assert max_d == 20251231
