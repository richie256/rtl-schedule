import zipfile
import pandas

import requests

import datetime
import time

import os
import os.path

from flask import Flask, abort, Response, jsonify, request
from flask_restful import Resource, Api

import logging

# create logger with 'rtl-schedule'
logger = logging.getLogger('rtl-schedule')

logger.setLevel(logging.DEBUG)
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
logger.addHandler(fh)
logger.addHandler(ch)

app = Flask(__name__)
api = Api(app)

class ParseRTLData:

    def __init__(self, schedule_zipfile='gtfs.zip'):

        file = os.getcwd() + '/' + schedule_zipfile

        if not (os.path.isfile(file)):
            self.downloadGtfsFile(file)
            logger.info("Downloaded a new zip file.")

        self.schedule_zipfile = schedule_zipfile


    def downloadGtfsFile(self, ZipFile_location) -> None:

        """ Download the GTFS file from the website, write it on disk. """

        input_url = "http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip"
        myfile = requests.get(input_url, allow_redirects=True)
         
        open(ZipFile_location, 'wb').write(myfile.content)

    def getStopId(self, stop_code: int) -> int:

        """ Retrieve the stop_id based on a stop_code """

        with zipfile.ZipFile(self.schedule_zipfile) as myzip:

            with myzip.open('stops.txt') as myfile:

                # pandas.read_csv(z.open(z.infolist()[0].filename))
                stops = pandas.read_csv(myfile, index_col='stop_code')

        stopId_cellvalue = stops.loc[stop_code, : "stop_id" ].values[0]

        return stopId_cellvalue

    def getServiceId(self, date) -> int:

        """ Retrive the service_id for a giving date """

        # Return the day of the week as an integer, where Monday is 0 and Sunday is 6.
        curr_weekday = date.weekday()

        currDateInt = int(date.strftime("%Y%m%d"))


        with zipfile.ZipFile(self.schedule_zipfile) as myzip:
            with myzip.open('calendar.txt') as myfile:

                dataframe = pandas.read_csv(myfile)

        for index, row in dataframe.iterrows():

            # Monday
            # if ((curr_weekday == 0) and (row["monday"] == 1) and (row["start_date"] <= currDateInt) and (row["end_date"] >= currDateInt)):
            if ((curr_weekday == 0) and (row["monday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Tuesday
            if ((curr_weekday == 1) and (row["tuesday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Wednesday
            if ((curr_weekday == 2) and (row["wednesday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Thursday
            if ((curr_weekday == 3) and (row["thursday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Friday
            if ((curr_weekday == 4) and (row["friday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Saturday
            if ((curr_weekday == 5) and (row["saturday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

            # Sunday
            if ((curr_weekday == 6) and (row["sunday"] == 1) and (row["end_date"] >= currDateInt)):
                return row["service_id"]

        # TODO: Unexpected, raise something
        return -1


    def getNextStop(self, stop_id: int, parm_datetime):

        """Retrieve the next stop information"""

        todayServiceId = self.getServiceId(parm_datetime.date())

        stop_times = None
        trips = None

        # Join stop_times.txt avec trips.txt (key trip_id), trim stop_id. create a new dataframe
        with zipfile.ZipFile(self.schedule_zipfile) as myzip:

            with myzip.open('stop_times.txt') as myfile1:

                stop_times = pandas.read_csv(myfile1, index_col='stop_id')

            # Only keep rows where stop_id is our stop_id.
            # Note using [[ ]] returns a DataFrame.
            stop_times = stop_times.loc[[stop_id, ]]

            with myzip.open('trips.txt') as myfile2:

                trips = pandas.read_csv(myfile2)

        results = stop_times.merge(trips, how='left', on='trip_id', validate='many_to_one')

        # Add a date field. (today).
        results['arrival_datetime'] = parm_datetime.date()

        #Only today result subset
        results = results.set_index('service_id')
        todayResults = results.loc[[todayServiceId, ]]
        todayResults = todayResults.reset_index()

        # First loop is to patch the time field, then update datetime.
        for index, row in todayResults.iterrows():

            row_date = row["arrival_datetime"]
            row_time_str = row["arrival_time"]

            if (row["arrival_time"][:2] == '24'):

                # We change the time as 00
                row_time_str = ("00" + row["arrival_time"][2:])
                todayResults.at[index , 'arrival_time'] = row_time_str

                row_date = row_date + datetime.timedelta(days=1)

            # Update the arrival datetime
            time_h = int(row_time_str[:2])
            time_m = int(row_time_str[3:5])
            time_s = int(row_time_str[6:8])

            row_time = datetime.time(hour=time_h, minute=time_m, second=time_s)
            row_datetime = datetime.datetime.combine(row_date, row_time)

            todayResults.at[index , 'arrival_datetime'] = row_datetime


        todayResults['arrival_datetime'] = pandas.to_datetime(todayResults.arrival_datetime)

        todayResults = todayResults.sort_values(by=['arrival_datetime'])

        found_row = None

        # Second loop is to find the next stop.
        for index, row in todayResults.iterrows():

            if (row['arrival_datetime'] <= parm_datetime):
                continue
            else:
                found_row = row
                break

        # Row found
        # logger.info(found_row)

        return found_row


class RtlScheduleNextStop(Resource):

    """ Get the next stop informations in JSON format. """

    def get(self, stop_code):
        rtl_data = ParseRTLData(schedule_zipfile='gtfs.zip')

        stop_id = rtl_data.getStopId(stop_code)

        # Retrieve the next stop information from now
        current_datetime = datetime.datetime.now().replace(microsecond=0)
        nextStopRow = rtl_data.getNextStop(stop_id, current_datetime)


        difference = nextStopRow.arrival_datetime - current_datetime
        seconds_in_day = 24 * 60 * 60
        nbr_minutes,nbr_seconds = divmod(difference.days * seconds_in_day + difference.seconds, 60)

        result = { 'nextstop_nbrmins': nbr_minutes,
                   'nextstop_nbrsecs': nbr_seconds,
                   'route_id': nextStopRow.route_id,
                   'arrival_time': nextStopRow.arrival_time,
                   'trip_headsign': nextStopRow.trip_headsign,
                   'current_time': str(current_datetime.time()),
                 }

        return jsonify(result)

api.add_resource(RtlScheduleNextStop, '/rtl_schedule/nextstop/<int:stop_code>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
