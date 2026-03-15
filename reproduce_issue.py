import unittest
from unittest.mock import patch, MagicMock
import os
import datetime
from zipfile import ZipFile
from io import BytesIO

from data_parser import ParseRTLData
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

    def create_gtfs_zip(self, calendar_data):
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('stops.txt', 'stop_id,stop_code,stop_name\n1,123,Test Stop 1')
            zf.writestr('calendar.txt', calendar_data)
            zf.writestr('stop_times.txt', 'trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,10:00:00,10:00:30,1,1')
            zf.writestr('trips.txt', 'route_id,service_id,trip_id,trip_headsign\n101,1,1,To Downtown')
        return zip_buffer.getvalue()

    @patch('data_parser.requests.get')
    @patch('data_parser.is_file_expired', return_value=False)
    def test_refresh_on_no_service_found(self, mock_is_file_expired, mock_requests_get):
        # 1. Initial data without March 15th 2026
        # March 15 2026 is a Sunday
        calendar_v1 = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20260101,20260310'
        
        # 2. Updated data with March 15th 2026
        calendar_v2 = 'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,1,1,20260101,20261231'
        
        zip_v1 = self.create_gtfs_zip(calendar_v1)
        zip_v2 = self.create_gtfs_zip(calendar_v2)

        # First download returns v1
        mock_response_v1 = MagicMock()
        mock_response_v1.content = zip_v1
        
        # Second download (on refresh) returns v2
        mock_response_v2 = MagicMock()
        mock_response_v2.content = zip_v2
        
        mock_requests_get.side_effect = [mock_response_v1, mock_response_v2]

        # Initialize parser (should call download for v1)
        parser = ParseRTLData()
        self.assertEqual(mock_requests_get.call_count, 1)

        # Attempt to get next stop for March 15th 2026
        test_datetime = datetime.datetime(2026, 3, 15, 9, 0, 0)
        
        # This should trigger a refresh because March 15th is not in v1
        # Mock is_file_expired to False to ensure it's the "force=True" that triggers it
        next_stop = parser.get_next_stop(1, test_datetime)
        
        self.assertIsNotNone(next_stop)
        self.assertEqual(mock_requests_get.call_count, 2)
        self.assertEqual(next_stop.arrival_time, '10:00:00')

if __name__ == '__main__':
    unittest.main()
