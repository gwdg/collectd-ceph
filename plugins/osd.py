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

#import collectd
import json
import traceback
import subprocess
import pprint
import os
import re

import base

class CephOSDPlugin(base.Base):

    def __init__(self):
        base.Base.__init__(self)
        self.prefix = 'ceph'
    
    def get_stats(self):
        """Retrieves stats from ceph osds"""

        asok_base_path  = '/var/run/ceph'

        cluster_name = 'ceph'

#        asok_path   = '/var/run/ceph/ceph-osd.30.asok'
        format      = 'json-pretty'

        prefix = self.prefix

        data            = {}
        data[prefix]    = {}

        osd_regex = '^%s\-osd\.(\d+)\.asok$' % cluster_name

        for asok in os.listdir(asok_base_path):

            osd_id = ''
            m = re.match(r'%s' % osd_regex, asok)
            if m:
                # Get osd_id for later
                osd_id = 'osd-' + m.group(1)
            else:
                # Ignore non osd sockets
                continue
            
            # Get perf data from socket
            asok_path   = asok_base_path + '/' + asok
            json_string = self.admin_socket(asok_path, ['perf', 'dump'], format)

#            print json_string

            json_hash = json.loads(json_string)

            # Create metric data to be returned to collectd
            
            data[prefix][osd_id] = {}

            data[prefix][osd_id]['osd']         = self.copy_stats(json_hash['osd'], '^op_')
            data[prefix][osd_id]['objecter']    = self.copy_stats(json_hash['objecter'], '^op_')
            data[prefix][osd_id]['filestore']   = self.copy_stats(json_hash['filestore'], '.*')


#        print pprint.pformat(data)

        return data

#try:
plugin = CephOSDPlugin()
#except Exception as exc:
#    collectd.error("ceph-osd: failed to initialize ceph osd plugin :: %s :: %s"
#            % (exc, traceback.format_exc()))

plugin.get_stats()

def configure_callback(conf):
    """Received configuration information"""
    plugin.config_callback(conf)

def read_callback():
    """Callback triggerred by collectd on read"""
    plugin.read_callback()

#collectd.register_config(configure_callback)
#collectd.register_read(read_callback, plugin.interval)



