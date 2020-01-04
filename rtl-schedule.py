
#import csv


import pandas



class ParseRTLData:



    def getStopId(self, stop_code):


        stops = pandas.read_csv('stops.txt', index_col='stop_id')
        stop = stops[stops.stop_code == stop_code]

        return stop.stop_id

        # print(df)

        # with open('stops.txt') as csv_file:
        #     csv_reader = csv.reader(csv_file, delimiter=',')


