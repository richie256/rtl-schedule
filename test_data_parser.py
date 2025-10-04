
import pytest
from unittest.mock import patch, MagicMock
import os
import datetime
import pandas as pd
from zipfile import ZipFile

from data_parser import ParseRTLData
from const import RTL_GTFS_ZIP_FILE

@pytest.fixture
def gtfs_zip_file():
    # Create a dummy gtfs.zip file for testing
    with ZipFile(RTL_GTFS_ZIP_FILE, 'w') as zf:
        stops_data = 'stop_id,stop_code,stop_name\n1,123,Test Stop 1\n2,456,Test Stop 2'
        zf.writestr('stops.txt', stops_data)

        calendar_data = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231'
        zf.writestr('calendar.txt', calendar_data)

        stop_times_data = 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1\n1,10:05:00,10:05:30,2,2'
        zf.writestr('stop_times.txt', stop_times_data)

        trips_data = 'route_id,service_id,trip_id,trip_headsign\n101,1,1,To Downtown'
        zf.writestr('trips.txt', trips_data)
    yield
    if os.path.exists(RTL_GTFS_ZIP_FILE):
        os.remove(RTL_GTFS_ZIP_FILE)

@patch('data_parser.is_file_expired', return_value=False)
def test_init_loads_data(mock_is_file_expired, gtfs_zip_file):
    parser = ParseRTLData()
    assert isinstance(parser.stops, pd.DataFrame)
    assert isinstance(parser.calendar, pd.DataFrame)
    assert isinstance(parser.stop_times, pd.DataFrame)
    assert isinstance(parser.trips, pd.DataFrame)
    assert not parser.stops.empty
    assert not parser.calendar.empty
    assert not parser.stop_times.empty
    assert not parser.trips.empty

@patch('data_parser.requests.get')
@patch('data_parser.is_file_expired', return_value=True)
def test_init_downloads_new_file(mock_is_file_expired, mock_requests_get, gtfs_zip_file):
    # Mock the response from requests.get
    mock_response = MagicMock()
    # Create a valid zip file in memory
    from io import BytesIO
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zf:
        zf.writestr('stops.txt', 'stop_id,stop_code,stop_name\n1,123,Test Stop 1')
        zf.writestr('calendar.txt', 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231')
        zf.writestr('stop_times.txt', 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1')
        zf.writestr('trips.txt', 'route_id,service_id,trip_id,trip_headsign\n101,1,1,To Downtown')
    mock_response.content = zip_buffer.getvalue()
    mock_requests_get.return_value = mock_response

    # Create a dummy gtfs.zip file to be overwritten
    with open(RTL_GTFS_ZIP_FILE, 'w') as f:
        f.write('old content')

    parser = ParseRTLData()

    mock_requests_get.assert_called_once()

@patch('data_parser.is_file_expired', return_value=False)
def test_get_stop_id(mock_is_file_expired, gtfs_zip_file):
    parser = ParseRTLData()
    stop_id = parser.get_stop_id(123)
    assert stop_id == 1

@patch('data_parser.is_file_expired', return_value=False)
def test_get_service_id(mock_is_file_expired, gtfs_zip_file):
    parser = ParseRTLData()
    # Monday in 2025
    test_date = datetime.date(2025, 9, 29)
    service_id = parser.get_service_id(test_date)
    assert service_id == 1

@patch('data_parser.is_file_expired', return_value=False)
def test_get_next_stop(mock_is_file_expired, gtfs_zip_file):
    parser = ParseRTLData()
    # Monday in 2025 at 9:00 AM
    test_datetime = datetime.datetime(2025, 9, 29, 9, 0, 0)
    next_stop = parser.get_next_stop(1, test_datetime)
    assert next_stop is not None
    assert next_stop.route_id == 101
    assert next_stop.arrival_time == '10:00:00'
