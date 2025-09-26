import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestMain(unittest.TestCase):

    @patch('main.rtl_data')
    def test_get_next_stop_success(self, mock_rtl_data):
        # Mock the data parser
        mock_rtl_data.get_stop_id.return_value = 1
        mock_next_stop_row = MagicMock()
        
        mock_arrival_datetime = MagicMock()
        mock_arrival_datetime.__sub__.return_value.total_seconds.return_value = 600

        mock_next_stop_row.arrival_datetime = mock_arrival_datetime
        mock_next_stop_row.route_id = 101
        mock_next_stop_row.arrival_time = '10:00:00'
        mock_next_stop_row.trip_headsign = 'To Downtown'
        mock_rtl_data.get_next_stop.return_value = mock_next_stop_row

        # Mock datetime to control the current time
        with patch('main.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value.replace.return_value = MagicMock()

            response = client.get("/rtl_schedule/nextstop/123")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['nextstop_nbrmins'], 10)
            self.assertEqual(data['route_id'], 101)

    @patch('main.rtl_data')
    def test_get_next_stop_no_more_buses(self, mock_rtl_data):
        mock_rtl_data.get_stop_id.return_value = 1
        mock_rtl_data.get_next_stop.return_value = None

        response = client.get("/rtl_schedule/nextstop/123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "No more buses for today"})

    @patch('main.mqtt_publisher_task')
    def test_start_mqtt_publisher(self, mock_mqtt_publisher_task):
        response = client.post("/start-mqtt-publisher?stop_code=123&mqtt_host=localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "MQTT publisher started in the background."})

if __name__ == '__main__':
    unittest.main()
