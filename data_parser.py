import datetime
import os
import zipfile
from typing import Optional

import requests
from pandas import read_csv, to_datetime, Series, errors
import pandas

from const import _LOGGER, RTL_GTFS_URL, RTL_GTFS_ZIP_FILE
from util import is_file_expired

class NoServiceFoundError(ValueError):
    """Exception raised when no service is found for a given date."""
    pass

class ParseRTLData:
    def __init__(self):
        self.schedule_zipfile = RTL_GTFS_ZIP_FILE
        _LOGGER.info(f"ParseRTLData init")
        
        self.data_dir = os.environ.get("GTFS_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
        self.file_path = os.path.join(self.data_dir, self.schedule_zipfile)
        self._load_data()

    def _load_data(self, force_download=False):
        """Download and load GTFS data into memory."""
        try:
            if force_download or not (os.path.isfile(self.file_path)) or is_file_expired(self.file_path):
                _LOGGER.info(f"Downloading a new zip file from [{RTL_GTFS_URL}]")
                self._download_gtfs_file(self.file_path)

            with zipfile.ZipFile(self.file_path) as my_zip:
                self.stops = read_csv(my_zip.open('stops.txt'), index_col='stop_code')
                self.calendar = read_csv(my_zip.open('calendar.txt'))
                self.stop_times = read_csv(my_zip.open('stop_times.txt'), index_col='stop_id')
                self.trips = read_csv(my_zip.open('trips.txt'))
        except FileNotFoundError:
            _LOGGER.error(f"GTFS file not found at {self.file_path}. Please check the file path and permissions.")
            raise
        except (zipfile.BadZipFile, pandas.errors.ParserError) as e:
            _LOGGER.error(f"An error occurred while parsing the GTFS file: {e}")
            raise

    def refresh(self, force=False):
        """Check if data needs to be refreshed and reload if necessary."""
        if force or is_file_expired(self.file_path):
            _LOGGER.info(f"Refreshing GTFS data (force={force})...")
            self._load_data(force_download=force)

    @staticmethod
    def _download_gtfs_file(zipfile_location) -> None:
        """ Download the GTFS file from the website, write it on disk. """
        my_file = requests.get(RTL_GTFS_URL, allow_redirects=True)
        with open(zipfile_location, 'wb') as my_zip:
            my_zip.write(my_file.content)

    def get_stop_id(self, stop_code: int) -> int:
        """ Retrieve the stop_id based on a stop_code """
        self.refresh()
        if stop_code not in self.stops.index:
            _LOGGER.error(f"Stop code {stop_code} not found in the GTFS data.")
            return None
        return self.stops.loc[stop_code, "stop_id"]

    def _get_service_id(self, date: datetime.date) -> int:
        """ Retrieve the service_id for a given date """
        curr_weekday = date.weekday()
        curr_date_int = int(date.strftime("%Y%m%d"))

        weekday_map = {
            0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
            4: "friday", 5: "saturday", 6: "sunday"
        }
        
        weekday_str = weekday_map.get(curr_weekday)

        if weekday_str:
            service = self.calendar[
                (self.calendar[weekday_str] == 1) &
                (self.calendar["end_date"] >= curr_date_int) &
                (self.calendar["start_date"] <= curr_date_int)
            ]
            if not service.empty:
                return service.iloc[0]["service_id"]
            
        raise NoServiceFoundError(f"No service found for date {date}")

    def _get_today_schedule(self, service_id: int, stop_id: int):
        """Get the schedule for a given service ID and stop ID."""
        stop_times_for_stop = self.stop_times.loc[self.stop_times.index == stop_id]
        results = stop_times_for_stop.merge(self.trips, how='left', on='trip_id', validate='many_to_one')
        return results[results['service_id'] == service_id].copy()

    def _calculate_arrival_datetimes(self, schedule, date):
        """Calculate the arrival datetimes for the schedule."""
        schedule['arrival_time'] = schedule['arrival_time'].str.replace('^24', '00', regex=True)
        
        def calculate_arrival(row):
            row_date = date
            if row["arrival_time"].startswith("00"):
                row_date = row_date + datetime.timedelta(days=1)
            
            time_h, time_m, time_s = map(int, row["arrival_time"].split(':'))
            
            try:
                row_time = datetime.time(hour=time_h, minute=time_m, second=time_s)
                return datetime.datetime.combine(row_date, row_time)
            except ValueError:
                return None

        schedule['arrival_datetime'] = schedule.apply(calculate_arrival, axis=1)
        return schedule.dropna(subset=['arrival_datetime']).sort_values(by=['arrival_datetime'])

    def get_next_stop(self, stop_id: int, parm_datetime: datetime.datetime) -> Optional[Series]:
        """Retrieve the next stop information"""
        self.refresh()
        _LOGGER.info(f"Retrieving next stop for stop_id {stop_id} at {parm_datetime}")

        try:
            today_service_id = self._get_service_id(parm_datetime.date())
        except NoServiceFoundError:
            # If no service found, try refreshing data once just in case the file was updated but not yet expired
            _LOGGER.info(f"No service found for {parm_datetime.date()}, attempting a forced refresh.")
            self.refresh(force=True)
            try:
                today_service_id = self._get_service_id(parm_datetime.date())
                _LOGGER.info(f"Successfully found service_id {today_service_id} after refresh.")
            except NoServiceFoundError as e:
                _LOGGER.error(f"Still no service found for {parm_datetime.date()} after refresh: {e}")
                return None

        today_schedule = self._get_today_schedule(today_service_id, stop_id)
        
        if today_schedule.empty:
            _LOGGER.info(f"No schedule found for service_id {today_service_id} and stop_id {stop_id}")
            return None

        today_schedule_with_arrivals = self._calculate_arrival_datetimes(today_schedule, parm_datetime.date())
        
        next_stop = today_schedule_with_arrivals[today_schedule_with_arrivals['arrival_datetime'] > parm_datetime]

        if not next_stop.empty:
            return next_stop.iloc[0]
        
        _LOGGER.info(f"No more buses for stop_id {stop_id} after {parm_datetime}")
        return None