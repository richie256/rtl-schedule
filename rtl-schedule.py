import zipfile
from pandas import read_csv, to_datetime

import requests

import os
import os.path

import time

from flask import Flask, jsonify
from flask_restful import Resource, Api

import paho.mqtt.publish as publish

import logging

import datetime

from const import _LOGGER, RTL_MQTT_MODE, RTL_JSON_MS_MODE

from util import is_file_expired

# create logger with 'rtl-schedule'
# logger = logging.getLogger('rtl-schedule')

_LOGGER.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('rtl-schedule.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
_LOGGER.addHandler(fh)
_LOGGER.addHandler(ch)

app = Flask(__name__)
api = Api(app)

run_mode = None
if os.environ.get('RTL_MODE') is not None and os.environ.get('RTL_MODE').lower() == RTL_MQTT_MODE:
    run_mode = RTL_MQTT_MODE
else:
    run_mode = RTL_JSON_MS_MODE


class ParseRTLData:
    def __init__(self, schedule_zipfile='gtfs.zip'):

        file = os.getcwd() + '/' + schedule_zipfile
        self.schedule_zipfile = schedule_zipfile

        # If the file doesn't exists or it is expired, download a new file.
        if not (os.path.isfile(file)) or is_file_expired(file):
            self.download_gtfs_file(file)
            _LOGGER.info("Downloaded a new zip file.")

    @staticmethod
    def download_gtfs_file(zipfile_location) -> None:

        """ Download the GTFS file from the website, write it on disk. """

        input_url = "http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip"
        my_file = requests.get(input_url, allow_redirects=True)

        my_zip = open(zipfile_location, 'wb')
        my_zip.write(my_file.content)
        my_zip.close()

    # def prepare_stop_gtfs_file(self, stop_id: int) -> None:
    #     """ Prepare a GTFS file for a specific stop id."""
    #
    #     self.stop_id_file = 'gtfs_' + str(stop_id) + '.zip'
    #
    #     if not os.path.isfile(self.stop_id_file) or is_file_expired(self.stop_id_file):
    #         pass
    #
    #     is_file_expired
    #
    #     # Check if exists
    #     pass
    #
    #     return

    def get_stop_id(self, stop_code: int) -> int:

        """ Retrieve the stop_id based on a stop_code """

        with zipfile.ZipFile(self.schedule_zipfile) as my_zip:
            with my_zip.open('stops.txt') as my_file:
                stops = read_csv(my_file, index_col='stop_code')

        stop_id_cell_value = stops.loc[stop_code, : "stop_id"].values[0]

        return stop_id_cell_value

    def get_service_id(self, date) -> int:

        """ Retrive the service_id for a giving date """

        # Return the day of the week as an integer, where Monday is 0 and Sunday is 6.
        curr_weekday = date.weekday()

        curr_date_int = int(date.strftime("%Y%m%d"))

        with zipfile.ZipFile(self.schedule_zipfile) as myzip:
            with myzip.open('calendar.txt') as myfile:
                dataframe = read_csv(myfile)

        for index, row in dataframe.iterrows():

            # Monday
            if (curr_weekday == 0) and (row["monday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Tuesday
            if (curr_weekday == 1) and (row["tuesday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Wednesday
            if (curr_weekday == 2) and (row["wednesday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Thursday
            if (curr_weekday == 3) and (row["thursday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Friday
            if (curr_weekday == 4) and (row["friday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Saturday
            if (curr_weekday == 5) and (row["saturday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

            # Sunday
            if (curr_weekday == 6) and (row["sunday"] == 1) and (row["end_date"] >= curr_date_int):
                return row["service_id"]

        # TODO: Unexpected, raise something
        return -1

    def get_next_stop(self, stop_id: int, parm_datetime):

        """Retrieve the next stop information"""

        today_service_id = self.get_service_id(parm_datetime.date())

        stop_times = None
        trips = None

        # Join stop_times.txt with trips.txt (key trip_id), trim stop_id. create a new dataframe
        with zipfile.ZipFile(self.schedule_zipfile) as my_zip:

            with my_zip.open('stop_times.txt') as my_file1:
                stop_times = read_csv(my_file1, index_col='stop_id')

            # Only keep rows where stop_id is our stop_id.
            # Note using [[ ]] returns a DataFrame.
            stop_times = stop_times.loc[[stop_id, ]]

            with my_zip.open('trips.txt') as my_file2:
                trips = read_csv(my_file2)

        results = stop_times.merge(trips, how='left', on='trip_id', validate='many_to_one')

        # Add a date field. (today).
        results['arrival_datetime'] = parm_datetime.date()

        # Only today result subset
        results = results.set_index('service_id')
        today_results = results.loc[[today_service_id, ]]
        today_results = today_results.reset_index()

        # First loop is to patch the time field, then update datetime.
        for index, row in today_results.iterrows():

            row_date = row["arrival_datetime"]
            row_time_str = row["arrival_time"]

            if row["arrival_time"][:2] == '24':
                # We change the time as 00
                row_time_str = ("00" + row["arrival_time"][2:])
                today_results.at[index, 'arrival_time'] = row_time_str

                row_date = row_date + datetime.timedelta(days=1)

            # Update the arrival datetime
            time_h = int(row_time_str[:2])
            time_m = int(row_time_str[3:5])
            time_s = int(row_time_str[6:8])

            row_time = datetime.time(hour=time_h, minute=time_m, second=time_s)
            row_datetime = datetime.datetime.combine(row_date, row_time)

            today_results.at[index, 'arrival_datetime'] = row_datetime

        today_results['arrival_datetime'] = to_datetime(today_results.arrival_datetime)

        today_results = today_results.sort_values(by=['arrival_datetime'])

        found_row = None

        # Second loop is to find the next stop.
        for index, row in today_results.iterrows():

            if row['arrival_datetime'] <= parm_datetime:
                continue
            else:
                found_row = row
                break

        # Row found
        # logger.info(found_row)

        return found_row


class RtlScheduleNextStop(Resource):
    """ Get the next stop information in JSON format. """

    def get(self, stop_code):
        rtl_data = ParseRTLData(schedule_zipfile='gtfs.zip')

        stop_id = rtl_data.get_stop_id(stop_code)

        # Retrieve the next stop information from now
        current_datetime = datetime.datetime.now().replace(microsecond=0)
        next_stop_row = rtl_data.get_next_stop(stop_id, current_datetime)

        difference = next_stop_row.arrival_datetime - current_datetime
        seconds_in_day = 24 * 60 * 60
        nbr_minutes, nbr_seconds = divmod(difference.days * seconds_in_day + difference.seconds, 60)

        result = {'nextstop_nbrmins': nbr_minutes,
                  'nextstop_nbrsecs': nbr_seconds,
                  'route_id': next_stop_row.route_id,
                  'arrival_time': next_stop_row.arrival_time,
                  'trip_headsign': next_stop_row.trip_headsign,
                  'current_time': str(current_datetime.time()),
                  }

        return jsonify(result)


def send_mqtt(topic, payload, host: str, port: int, auth):
    try:
        publish.single(topic, payload=payload, qos=0, hostname=host,
                       port=port, auth=auth)
    except Exception as ex:
        _LOGGER.info("MQTT Publish Failed: " + str(ex))


class RtlScheduleNextStopMQTT:

    def __init__(self, stop_code: int):
        self.rtl_data = ParseRTLData(schedule_zipfile='gtfs.zip')

        self.stop_code = stop_code
        self.next_stop_row = None
        self.nbr_minutes = None
        self.nbr_seconds = None

        self.stop_id = self.rtl_data.get_stop_id(self.stop_code)

        # Retrieve the next stop information from now
        self.current_datetime = datetime.datetime.now().replace(microsecond=0)

    def retrieve(self):
        self.next_stop_row = self.rtl_data.get_next_stop(self.stop_id, self.current_datetime)

        difference = self.next_stop_row.arrival_datetime - self.current_datetime
        seconds_in_day = 24 * 60 * 60
        self.nbr_minutes, self.nbr_seconds = divmod(difference.days * seconds_in_day + difference.seconds, 60)

    def publish(self, host: str, port: int, authentication):
        _LOGGER.info("publish({}, {}, {})".format(host, port, authentication))

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/arrival_time',
            '{}'.format(self.next_stop_row.arrival_time),
            host,
            port,
            authentication
        )

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/current_datetime',
            '{}'.format(self.current_datetime),
            host,
            port,
            authentication
        )

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/nextstop_nbrmins',
            '{}'.format(self.nbr_minutes),
            host,
            port,
            authentication
        )

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/nextstop_nbrsecs',
            '{}'.format(self.nbr_seconds),
            host,
            port,
            authentication
        )

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/route_id',
            '{}'.format(self.next_stop_row.route_id),
            host,
            port,
            authentication
        )

        send_mqtt(
            'schedule/bus_stop/' + str(self.stop_code) + '/trip_headsign',
            '{}'.format(self.next_stop_row.trip_headsign),
            host,
            port,
            authentication
        )

    # send data to MQTT broker defined in settings


if run_mode == RTL_JSON_MS_MODE:
    api.add_resource(RtlScheduleNextStop, '/rtl_schedule/nextstop/<int:stop_code>')

if __name__ == '__main__':
    if run_mode == RTL_JSON_MS_MODE:
        app.run(host='0.0.0.0', port=80, debug=True)

    if run_mode == RTL_MQTT_MODE:
        _LOGGER.info("MQTT mode...")
        mqtt_host = os.environ.get('MQTT_HOST')
        if os.environ.get('MQTT_PORT') is None:
            mqtt_port = 1883
        else:
            mqtt_port = int(os.environ.get('MQTT_PORT'))

        stop_code = None

        if os.environ.get('RTL_STOP_CODE') is not None:
            stop_code = int(os.environ.get('RTL_STOP_CODE'))
            _LOGGER.info("stop_code: " + str(stop_code))
        else:
            # TODO: Raise something.
            _LOGGER.info("Unexpected...")
            pass

        auth = None
        if os.environ.get('MQTT_USERNAME') is not None and os.environ.get('MQTT_PASSWORD') is not None:
            auth = {'username': os.environ.get('MQTT_USERNAME'), 'password': os.environ.get('MQTT_PASSWORD')}

        while True:
            rtl_mqtt = RtlScheduleNextStopMQTT(stop_code)

            rtl_mqtt.retrieve()
            rtl_mqtt.publish(mqtt_host, mqtt_port, auth)

            time.sleep(20)
