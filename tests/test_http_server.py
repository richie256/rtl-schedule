import datetime
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from rtl_schedule.http_server import create_app


@pytest.fixture
def mock_rtl_data():
    return MagicMock()

@pytest.fixture
def client(mock_rtl_data):
    app = create_app(rtl_data=mock_rtl_data)
    app.config['TESTING'] = True
    return app.test_client()

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}

@freeze_time("2026-03-16 08:00:00")
def test_get_next_stop_success(client, mock_rtl_data):
    stop_code = 32752
    mock_rtl_data.get_stop_id.return_value = "stop_id_123"
    
    # We are at 08:00:00
    arrival_dt = datetime.datetime(2026, 3, 16, 8, 15, 0)
    mock_next_stop = MagicMock()
    mock_next_stop.arrival_datetime = arrival_dt
    mock_next_stop.arrival_time = "08:15:00"
    mock_next_stop.route_id = 44
    mock_next_stop.trip_headsign = "Terminus Panama"
    
    mock_rtl_data.get_next_stop.return_value = mock_next_stop
    
    response = client.get(f'/rtl_schedule/nextstop/{stop_code}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['nextstop_nbrmins'] == 15
    assert data['nextstop_nbrsecs'] == 0
    assert data['route_id'] == 44
    assert data['arrival_time'] == "08:15:00"

def test_get_next_stop_invalid_code(client):
    response = client.get('/rtl_schedule/nextstop/0')
    assert response.status_code == 400
    assert "error" in response.get_json()

def test_get_next_stop_not_found(client, mock_rtl_data):
    mock_rtl_data.get_stop_id.return_value = None
    response = client.get('/rtl_schedule/nextstop/99999')
    assert response.status_code == 404
    assert response.get_json() == {"error": "Stop code not found"}

def test_get_next_stop_no_more_buses(client, mock_rtl_data):
    mock_rtl_data.get_stop_id.return_value = "stop_id_123"
    mock_rtl_data.get_next_stop.return_value = None
    response = client.get('/rtl_schedule/nextstop/32752')
    assert response.status_code == 200
    assert response.get_json() == {"error": "No more buses for today"}
