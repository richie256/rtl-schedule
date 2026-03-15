import unittest
from unittest.mock import patch, MagicMock
import os
import datetime
from zipfile import ZipFile
from io import BytesIO

from data_parser import ParseRTLData, NoServiceFoundError
from const import RTL_GTFS_ZIP_FILE

class TestIssueReproduction(unittest.TestCase):
    def setUp(self):
        self.zip_file = RTL_GTFS_ZIP_FILE
        # Ensure no zip file exists initially
        if os.path.exists(self.zip_file):
            os.remove(self.zip_file)

    def tearDown(self):
        if os.path.exists(self.zip_file):
            os.remove(self.zip_file)

    def create_gtfs_zip(self, calendar_data, calendar_dates_data=None):
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('stops.txt', 'stop_id,stop_code,stop_name\n1,123,Test Stop 1')
            zf.writestr('calendar.txt', calendar_data)
            if calendar_dates_data:
                zf.writestr('calendar_dates.txt', calendar_dates_data)
            zf.writestr('stop_times.txt', 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1\n2,11:00:00,11:00:30,1,1')
            zf.writestr('trips.txt', 'route_id,service_id,trip_id,trip_headsign\n101,1,1,To Downtown\n101,2,2,To Uptown')
        return zip_buffer.getvalue()

    @patch('data_parser.requests.get')
    @patch('data_parser.is_file_expired', return_value=False)
    def test_calendar_dates_addition(self, mock_is_file_expired, mock_requests_get):
        # Service 1 is NOT active on Sundays
        calendar = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20260101,20261231'
        # But we add service 2 for March 15th (a Sunday)
        calendar_dates = 'service_id,date,exception_type\n2,20260315,1'
        
        zip_content = self.create_gtfs_zip(calendar, calendar_dates)
        mock_response = MagicMock()
        mock_response.content = zip_content
        mock_requests_get.return_value = mock_response

        parser = ParseRTLData()
        test_datetime = datetime.datetime(2026, 3, 15, 9, 0, 0)
        next_stop = parser.get_next_stop(1, test_datetime, stop_code=123)
        
        self.assertIsNotNone(next_stop)
        self.assertEqual(next_stop.service_id, 2)
        self.assertEqual(next_stop.arrival_time, '11:00:00')

    @patch('data_parser.requests.get')
    @patch('data_parser.is_file_expired', return_value=False)
    def test_calendar_dates_removal(self, mock_is_file_expired, mock_requests_get):
        # Service 1 is active on Sundays
        calendar = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,1,1,20260101,20261231'
        # But we remove service 1 for March 15th
        calendar_dates = 'service_id,date,exception_type\n1,20260315,2'
        
        zip_content = self.create_gtfs_zip(calendar, calendar_dates)
        mock_response = MagicMock()
        mock_response.content = zip_content
        mock_requests_get.return_value = mock_response

        parser = ParseRTLData()
        test_datetime = datetime.datetime(2026, 3, 15, 9, 0, 0)
        
        # Should raise NoServiceFoundError (caught by get_next_stop and returning None)
        # after failing to find a service even after a "forced refresh" (which we mock here as just returning the same content)
        next_stop = parser.get_next_stop(1, test_datetime, stop_code=123)
        self.assertIsNone(next_stop)

    @patch('data_parser.requests.get')
    @patch('data_parser.is_file_expired', return_value=False)
    @patch('data_parser.HastusScraper.get_schedule')
    def test_scraper_fallback(self, mock_get_schedule, mock_is_file_expired, mock_requests_get):
        # 1. GTFS data without March 15th
        calendar = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20260101,20260310'
        zip_content = self.create_gtfs_zip(calendar)
        
        mock_response = MagicMock()
        mock_response.content = zip_content
        mock_requests_get.return_value = mock_response

        # 2. Scraper returns a time for March 15th
        target_date = datetime.date(2026, 3, 15)
        arrival_time = datetime.datetime.combine(target_date, datetime.time(10, 30))
        mock_get_schedule.return_value = [arrival_time]

        parser = ParseRTLData()
        test_datetime = datetime.datetime(2026, 3, 15, 9, 0, 0)
        
        # Should fallback to scraper
        next_stop = parser.get_next_stop(1, test_datetime, stop_code=123)
        
        self.assertIsNotNone(next_stop)
        self.assertEqual(next_stop.trip_headsign, "Live Schedule")
        self.assertEqual(next_stop.arrival_time, "10:30:00")
        mock_get_schedule.assert_called_once_with(1, target_date)

if __name__ == '__main__':
    unittest.main()
