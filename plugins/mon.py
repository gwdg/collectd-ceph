#!/usr/bin/env python
#
# vim: tabstop=4 shiftwidth=4

# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; only version 2 of the License is applicable.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# Authors:
#   Ricardo Rocha <ricardo@catalyst.net.nz>
#
# About this plugin:
#   This plugin collects information regarding Ceph OSDs.
#
# collectd:
#   http://collectd.org
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml
# ceph osds:
#   http://ceph.com/docs/master/rados/operations/monitoring/#checking-osd-status
#

import collectd
import json
import traceback
import subprocess
import pprint
import os
import re

import base

class CephMONPlugin(base.Base):

    def __init__(self):
        base.Base.__init__(self)
        self.prefix = 'ceph'
    
    def get_stats(self):
        """Retrieves stats from ceph mons"""

        asok_base_path  = '/var/run/ceph'

        cluster_name = 'ceph'

        format      = 'json'

        prefix = self.prefix

        data            = {}
        data[prefix]    = {}

        mon_regex = '^%s\-mon\.(.+)\.asok$' % cluster_name

        for asok in os.listdir(asok_base_path):

            m = re.match(r'%s' % mon_regex, asok)
            if not m:
                # Ignore non mon sockets
                continue
            
            # Get perf data from socket
            asok_path   = asok_base_path + '/' + asok
            json_string = self.admin_socket(asok_path, ['perf', 'dump'], format)

#            print json_string

            json_hash = json.loads(json_string)

            # Create stats data to be returned to collectd
            
            data[prefix] = {}

            data[prefix]['cluster'] =       self.copy_stats(json_hash['cluster'], '^num_osd')
            data[prefix]['cluster'].update( self.copy_stats(json_hash['cluster'], '^osd_'))
            data[prefix]['cluster'].update( self.copy_stats(json_hash['cluster'], '^num_pg_'))
            data[prefix]['cluster'].update( self.copy_stats(json_hash['cluster'], '^num_object'))

#        print pprint.pformat(data)

        return data

try:
    plugin = CephMONPlugin()
except Exception as exc:
    collectd.error("ceph-osd: failed to initialize ceph osd plugin :: %s :: %s"
            % (exc, traceback.format_exc()))

plugin.get_stats()

def configure_callback(conf):
    """Received configuration information"""
    plugin.config_callback(conf)

def read_callback():
    """Callback triggerred by collectd on read"""
    plugin.read_callback()

collectd.register_config(configure_callback)
collectd.register_read(read_callback, plugin.interval)
