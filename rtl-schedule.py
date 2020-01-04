
#import csv

import zipfile

import pandas
# import numpy

# import wget
import requests

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

        logger.error("os.getcwd():" + os.getcwd())

        file = os.getcwd() + '/' + schedule_zipfile

        if not (os.path.isfile(file)):
            self.downloadGtfsFile(file)

        self.schedule_zipfile = schedule_zipfile


    def downloadGtfsFile(self, ZipFile_location):
        input_url = "http://www.rtl-longueuil.qc.ca/transit/latestfeed/RTL.zip"
        # wget.download(input_url, ZipFile)


         
        # url = 'https://readthedocs.org/projects/python-guide/downloads/pdf/latest/'
         
        myfile = requests.get(input_url, allow_redirects=True)
         
        open(ZipFile_location, 'wb').write(myfile.content)

        logger.info("Downloaded a new zip file.")





    def getStopId(self, stop_code):

        z = zipfile.ZipFile(self.schedule_zipfile)

        # pandas.read_csv(z.open(z.infolist()[0].filename))

        file = z.open('stops.txt')

        # stops = pandas.read_csv(file, index_col='stop_id')
        stops = pandas.read_csv(file, index_col='stop_code')



        row = stops.loc[stop_code, : ]

        stopId_cellvalue = stops.loc[stop_code, : "stop_id" ].values[0]



        # stop = stops.index(stop_code)
        # stop = stops[stop_code == stop_code]
        # stop = stops[stop_code == 32752]

        # stop = numpy.where(stop_code == stop_code)
        # stop = numpy.where(stops == 32752)

        # logger.error(str(stops))
        # logger.error(str(row))
        # logger.error(type(row))
        logger.error(str(stopId_cellvalue))
        logger.error(type(stopId_cellvalue))

        return str(stopId_cellvalue)
        # logger.error("Response: %s" % (stop.stop_id))
        # return stop.stop_id


class RtlScheduleNextStop(Resource):

    def get(self, stop_code):
        rtl_data = ParseRTLData(schedule_zipfile='gtfs.zip')
        # return rtl_data.getStopId(stop_code)

        return Response(rtl_data.getStopId(stop_code), mimetype='text/xml')



api.add_resource(RtlScheduleNextStop, '/rtl_schedule/nextstop/<int:stop_code>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
