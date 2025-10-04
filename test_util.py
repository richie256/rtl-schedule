
import pytest
from unittest.mock import patch
import os
import json
import datetime

from util import get_modification_date, is_file_expired, settings_from_file

@pytest.fixture
def test_file():
    test_file = "test_settings.json"
    yield test_file
    if os.path.exists(test_file):
        os.remove(test_file)

@patch('util.os.path.getmtime')
def test_get_modification_date(mock_getmtime):
    mock_getmtime.return_value = 1678886400  # March 15, 2023 12:00:00 PM
    expected_date = datetime.datetime.fromtimestamp(1678886400)
    assert get_modification_date("any_file.txt") == expected_date

from freezegun import freeze_time

@freeze_time("2023-03-15 13:00:00")
def test_is_file_expired(mocker):
    mocker.patch('util.os.path.isfile', return_value=True)
    
    # Case 1: File is not expired
    mocker.patch('util.get_modification_date', return_value=datetime.datetime(2023, 3, 15, 12, 0, 0))
    assert not is_file_expired("any_file.txt")

    # Case 2: File is expired
    mocker.patch('util.get_modification_date', return_value=datetime.datetime(2023, 3, 14, 12, 0, 0))
    assert is_file_expired("any_file.txt")

    # Case 3: File does not exist
    mocker.patch('util.os.path.isfile', return_value=False)
    assert is_file_expired("any_file.txt")

def test_settings_from_file_read_write(test_file):
    # Test writing to a file
    config_to_write = {"key": "value", "number": 123}
    assert settings_from_file(test_file, config_to_write)

    # Test reading from the file
    read_config = settings_from_file(test_file)
    assert read_config == config_to_write

def test_settings_from_file_read_nonexistent():
    # Test reading from a non-existent file
    read_config = settings_from_file("non_existent_file.json")
    assert read_config == {}
