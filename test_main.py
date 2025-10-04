import pytest
from unittest.mock import patch, MagicMock
from main import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch('main.rtl_data')
def test_get_next_stop_success(mock_rtl_data, client):
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
        assert response.status_code == 200
        data = response.get_json()
        assert data['nextstop_nbrmins'] == 10
        assert data['route_id'] == 101

@patch('main.rtl_data')
def test_get_next_stop_no_more_buses(mock_rtl_data, client):
    mock_rtl_data.get_stop_id.return_value = 1
    mock_rtl_data.get_next_stop.return_value = None

    response = client.get("/rtl_schedule/nextstop/123")
    assert response.status_code == 200
    assert response.get_json() == {"error": "No more buses for today"}
