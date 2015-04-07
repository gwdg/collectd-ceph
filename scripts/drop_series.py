#
# list / delete series by regexp utilizing influxdb-python client
#
# Works with InfluxDB v0.8.x, probably does not work with v0.9.x
#
# install influxdb-python:
#
# pip install influxdb --proxy=http://www-cache.gwdg.de:3128
#

import argparse

from influxdb.influxdb08 import InfluxDBClient

def drop_series(client, name):
    print 'droping series "%s"' % name
    query = 'drop series "%s"' % name
    client.query(query)

def main(args):
    user        = 'root'
    password    = 'root'
    dbname      = 'carbon'

    query       = 'list series'

    if args.select:
        query += ' /%s/' % args.select

    client = InfluxDBClient(args.host, args.port, user, password, dbname)

    result = client.query(query)

    if args.drop_series:
        for series in result[0]['points']:
            series_name = "%s" % series[1]
#            client.delete_series(series_name)
            drop_series(client, series_name)
    else:
        # Print result
        for series in result[0]['points']:
            print series[1]


def parse_args():
        parser = argparse.ArgumentParser(
                description='list / drop InfluxDB series by regexp')

        parser.add_argument(
            '--host', 
            type        = str, 
            required    = False, 
            default     = 'localhost',
            help        = 'hostname of InfluxDB http API')

        parser.add_argument(
            '--port', 
            type        = int, 
            required    = False, 
            default     = 8086,
            help        ='port of InfluxDB http API')

        parser.add_argument(
            '--drop-series',
            action      = 'store_true',
            default     = False,
            help        = 'Do not modify system state, just print commands to be run (default false)')

        parser.add_argument(
            '--select', 
            type        = str,       
            required    = False,
            help        = 'regexp for series selection')

        return parser.parse_args()

if __name__ == '__main__':
        args = parse_args()
        main(args)
