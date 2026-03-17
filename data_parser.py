import datetime
import os
import zipfile
from typing import Optional

import requests
from pandas import read_csv, to_datetime, Series, errors
import pandas

from const import _LOGGER, RTL_GTFS_URL, RTL_GTFS_ZIP_FILE
from util import is_file_expired
from hastus_scraper import HastusScraper

class NoServiceFoundError(ValueError):
    """Exception raised when no service is found for a given date."""
    pass

class ParseRTLData:
    def __init__(self):
        self.schedule_zipfile = RTL_GTFS_ZIP_FILE
        _LOGGER.info(f"ParseRTLData init")
        
        self.data_dir = os.environ.get("GTFS_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
        self.file_path = os.path.join(self.data_dir, self.schedule_zipfile)
        self.scraper = HastusScraper()
        self._load_data()

    def _load_data(self, force_download=False):
        """Download and load GTFS data into memory."""
        try:
            if force_download or not (os.path.isfile(self.file_path)) or is_file_expired(self.file_path):
                _LOGGER.info(f"Downloading a new zip file from [{RTL_GTFS_URL}]")
                self._download_gtfs_file(self.file_path)

            with zipfile.ZipFile(self.file_path) as my_zip:
                _LOGGER.info(f"Loading GTFS data from {self.file_path} into memory...")
                self.stops = read_csv(my_zip.open('stops.txt'), index_col='stop_code')
                self.calendar = read_csv(my_zip.open('calendar.txt'))
                self.stop_times = read_csv(my_zip.open('stop_times.txt'), index_col='stop_id')
                self.trips = read_csv(my_zip.open('trips.txt'))
                
                # Calculate global schedule range for diagnostics
                self.min_date = self.calendar['start_date'].min()
                self.max_date = self.calendar['end_date'].max()

                _LOGGER.info(f"Successfully loaded stops ({len(self.stops)}), calendar ({len(self.calendar)}), stop_times ({len(self.stop_times)}), and trips ({len(self.trips)})")
                _LOGGER.info(f"Global GTFS schedule range: {self.min_date} to {self.max_date}")
                
                # Load calendar_dates if it exists (it's optional in GTFS but common in RTL)
                try:
                    self.calendar_dates = read_csv(my_zip.open('calendar_dates.txt'))
                    _LOGGER.info(f"Loaded calendar_dates.txt ({len(self.calendar_dates)} entries)")
                except KeyError:
                    self.calendar_dates = pandas.DataFrame(columns=['service_id', 'date', 'exception_type'])
                    _LOGGER.info("calendar_dates.txt not found in GTFS, using empty DataFrame")

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
        """ Retrieve the service_id for a given date, handling exceptions in calendar_dates.txt """
        curr_weekday = date.weekday()
        curr_date_int = int(date.strftime("%Y%m%d"))

        # 1. Check calendar_dates.txt for explicit additions (exception_type=1)
        if not self.calendar_dates.empty:
            added_service = self.calendar_dates[
                (self.calendar_dates["date"] == curr_date_int) &
                (self.calendar_dates["exception_type"] == 1)
            ]
            if not added_service.empty:
                return added_service.iloc[0]["service_id"]

        # 2. Check calendar.txt for regular service
        weekday_map = {
            0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
            4: "friday", 5: "saturday", 6: "sunday"
        }
        weekday_str = weekday_map.get(curr_weekday)

        if weekday_str:
            regular_services = self.calendar[
                (self.calendar[weekday_str] == 1) &
                (self.calendar["end_date"] >= curr_date_int) &
                (self.calendar["start_date"] <= curr_date_int)
            ]
            
            # 3. Filter out regular services that are explicitly removed in calendar_dates.txt (exception_type=2)
            for _, service_row in regular_services.iterrows():
                service_id = service_row["service_id"]
                if not self.calendar_dates.empty:
                    removed_service = self.calendar_dates[
                        (self.calendar_dates["service_id"] == service_id) &
                        (self.calendar_dates["date"] == curr_date_int) &
                        (self.calendar_dates["exception_type"] == 2)
                    ]
                    if not removed_service.empty:
                        continue # This service is removed for today
                
                return service_id
            
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

    def _get_stop_date_range(self, stop_id: int):
        """Find the oldest and newest dates in the schedule for a given stop_id."""
        # 1. Get all trip_ids for this stop
        stop_times_for_stop = self.stop_times.loc[self.stop_times.index == stop_id]
        if stop_times_for_stop.empty:
            return None, None
        
        trip_ids = stop_times_for_stop['trip_id'].unique()
        
        # 2. Get all service_ids for these trips
        service_ids = self.trips[self.trips['trip_id'].isin(trip_ids)]['service_id'].unique()
        
        # 3. Find date ranges in calendar.txt
        relevant_calendar = self.calendar[self.calendar['service_id'].isin(service_ids)]
        min_date = relevant_calendar['start_date'].min() if not relevant_calendar.empty else None
        max_date = relevant_calendar['end_date'].max() if not relevant_calendar.empty else None
        
        # 4. Find date ranges in calendar_dates.txt
        if not self.calendar_dates.empty:
            relevant_dates = self.calendar_dates[self.calendar_dates['service_id'].isin(service_ids)]
            if not relevant_dates.empty:
                min_exception = relevant_dates['date'].min()
                max_exception = relevant_dates['date'].max()
                
                if min_date is None or min_exception < min_date:
                    min_date = min_exception
                if max_date is None or max_exception > max_date:
                    max_date = max_exception
        
        return min_date, max_date

    def get_next_stop(self, stop_id: int, parm_datetime: datetime.datetime, stop_code: Optional[int] = None) -> Optional[Series]:
        """Retrieve the next stop information"""
        self.refresh()
        
        # If stop_code isn't provided, try to find it from stop_id (inefficient but good for logs)
        if stop_code is None:
            matches = self.stops[self.stops['stop_id'] == stop_id]
            if not matches.empty:
                stop_code = matches.index[0]

        display_stop = f"{stop_code} (ID: {stop_id})" if stop_code else f"ID: {stop_id}"
        _LOGGER.info(f"Retrieving next stop for stop {display_stop} at {parm_datetime}")

        try:
            today_service_id = self._get_service_id(parm_datetime.date())
            today_schedule = self._get_today_schedule(today_service_id, stop_id)
            
            if today_schedule.empty:
                raise NoServiceFoundError(f"Empty schedule for service_id {today_service_id}")

            today_schedule_with_arrivals = self._calculate_arrival_datetimes(today_schedule, parm_datetime.date())
            
            # Filter for "Direction Terminus Panama" if requested
            # Note: trip_headsign in GTFS usually contains the direction
            target_direction = "Direction Terminus Panama"
            today_schedule_with_arrivals = today_schedule_with_arrivals[
                today_schedule_with_arrivals['trip_headsign'].str.contains(target_direction, case=False, na=False)
            ]

            next_stop = today_schedule_with_arrivals[today_schedule_with_arrivals['arrival_datetime'] > parm_datetime]

            if not next_stop.empty:
                result = next_stop.iloc[0].copy()
                result['retrieve_method'] = 'GTFS'
                return result
            
            _LOGGER.info(f"No more buses in GTFS for stop {display_stop} after {parm_datetime}")

        except NoServiceFoundError as e:
            _LOGGER.info(f"GTFS check failed for {parm_datetime.date()}: {e}. Trying live scraper fallback...")
            
        # Fallback to Hastus Scraper
        live_arrivals = self.scraper.get_schedule(stop_id, parm_datetime.date())
        if live_arrivals:
            _LOGGER.info(f"Found {len(live_arrivals)} arrivals via live scraper for stop {display_stop}")
            for arrival_obj in live_arrivals:
                if arrival_obj['arrival_datetime'] > parm_datetime:
                    # Return a Series-like object compatible with existing code
                    return Series({
                        'arrival_datetime': arrival_obj['arrival_datetime'],
                        'arrival_time': arrival_obj['arrival_time'],
                        'route_id': arrival_obj['route_id'],
                        'trip_headsign': arrival_obj['trip_headsign'],
                        'retrieve_method': 'live scraper'
                    })

        min_d, max_d = self._get_stop_date_range(stop_id)
        _LOGGER.error(f"No service found for {parm_datetime.date()} (GTFS & Live). Global GTFS range: {self.min_date} to {self.max_date}. Stop {display_stop} range: {min_d} to {max_d}")
        return None