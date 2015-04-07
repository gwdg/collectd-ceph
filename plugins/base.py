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
#   Helper object for all plugins.
#
# collectd:
#   http://collectd.org
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml
#

import collectd
import datetime
import traceback
import socket
import json
import struct
import re

from ceph_argparse import parse_json_funcsigs, validate_command


class Base(object):

    def __init__(self):
        self.verbose = False
        self.debug = False
        self.prefix = ''
        self.cluster = 'ceph'
        self.testpool = 'test'
        self.interval = 60.0

    def config_callback(self, conf):
        """Takes a collectd conf object and fills in the local config."""
        for node in conf.children:
            if node.key == "Verbose":
                if node.values[0] in ['True', 'true']:
                    self.verbose = True
            elif node.key == "Debug":
                if node.values[0] in ['True', 'true']:
                    self.debug = True
            elif node.key == "Prefix":
                self.prefix = node.values[0]
            elif node.key == 'Cluster':
                self.cluster = node.values[0]
            elif node.key == 'TestPool':
                self.testpool = node.values[0]
            elif node.key == 'Interval':
                self.interval = float(node.values[0])
            else:
                collectd.warning("%s: unknown config key: %s" % (self.prefix, node.key))

    def dispatch(self, stats):
        """
        Dispatches the given stats.

        stats should be something like:

        {'plugin': {'plugin_instance': {'type': {'type_instance': <value>, ...}}}}
        """
        if not stats:
            collectd.error("%s: failed to retrieve stats" % self.prefix)
            return

        self.logdebug("dispatching %d new stats :: %s" % (len(stats), stats))
        try:
            for plugin in stats.keys():
                for plugin_instance in stats[plugin].keys():
                    for type in stats[plugin][plugin_instance].keys():
                        type_value = stats[plugin][plugin_instance][type]
                        if not isinstance(type_value, dict):
                            self.dispatch_value(plugin, plugin_instance, type, None, type_value)
                        else:
                          for type_instance in stats[plugin][plugin_instance][type].keys():
                              self.dispatch_value(plugin, plugin_instance,
                                      type, type_instance,
                                      stats[plugin][plugin_instance][type][type_instance])
        except Exception as exc:
            collectd.error("%s: failed to dispatch values :: %s :: %s"
                    % (self.prefix, exc, traceback.format_exc()))

    def dispatch_value(self, plugin, plugin_instance, type, type_instance, value):
        """Looks for the given stat in stats, and dispatches it"""
        self.logdebug("dispatching value %s.%s.%s.%s=%s"
                % (plugin, plugin_instance, type, type_instance, value))

        val = collectd.Values(type='gauge')
        val.plugin=plugin
        val.plugin_instance=plugin_instance
        if type_instance is not None:
            val.type_instance="%s-%s" % (type, type_instance)
        else:
            val.type_instance=type
        val.values=[value]
        val.interval = self.interval
        val.dispatch()
        self.logdebug("sent metric %s.%s.%s.%s.%s"
                % (plugin, plugin_instance, type, type_instance, value))

    #
    # From /usr/bin/ceph: do socket IO against a ceph admin socket
    #
    # We copy / paste the code instead of just invoking /usr/bin/ceph to prevent a python interpreter start everytime
    #
    def admin_socket(self, asok_path, cmd, format=''):
        """
        Send a daemon (--admin-daemon) command 'cmd'.  asok_path is the
        path to the admin socket; cmd is a list of strings; format may be
        set to one of the formatted forms to get output in that form
        (daemon commands don't support 'plain' output).
        """

        def do_sockio(path, cmd):
            """ helper: do all the actual low-level stream I/O """
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(path)
            try:
                sock.sendall(cmd + '\0')
                len_str = sock.recv(4)
                if len(len_str) < 4:
                    raise RuntimeError("no data returned from admin socket")
                l, = struct.unpack(">I", len_str)
                ret = ''

                got = 0
                while got < l:
                    bit = sock.recv(l - got)
                    ret += bit
                    got += len(bit)

            except Exception as e:
                raise RuntimeError('exception: ' + str(e))
            return ret

        try:
            cmd_json = do_sockio(asok_path,
                json.dumps({"prefix":"get_command_descriptions"}))
        except Exception as e:
            raise RuntimeError('exception getting command descriptions: ' + str(e))

        if cmd == 'get_command_descriptions':
            return cmd_json

        sigdict = parse_json_funcsigs(cmd_json, 'cli')
        valid_dict = validate_command(sigdict, cmd)
        if not valid_dict:
            raise RuntimeError('invalid command')

        if format:
            valid_dict['format'] = format

        try:
            ret = do_sockio(asok_path, json.dumps(valid_dict))
        except Exception as e:
            raise RuntimeError('exception: ' + str(e))

        return ret

    def copy_stats(self, source_hash, selection):
        """
        Copy stats from source_hash to target_hash based on applying the selection regex against the names
        in the hash at the root level on the source hash.

        Additonally, the following transformations are applied:

        - For stat names ending in latency and referencing a hash the latency is calculated and substitutes 
          the hash in the target hash
        """

        target_hash = {}

        for key in source_hash.keys():

            stat_name   = key
            stat_value  = source_hash[key]

#            print 'Checking stat "%s"' % stat_name

            if not re.match(r'%s' % selection, stat_name):
                # Ignore not selected stats
                continue

            # Process latency
            if isinstance(stat_value, dict):
                lat_sum         = float(stat_value['sum'])
                lat_avgcount    = float(stat_value['avgcount'])
                if lat_avgcount == 0:
                    target_hash[stat_name] = 0
                else:
                    target_hash[stat_name] = lat_sum / lat_avgcount
                continue

            # Process simple stats
            target_hash[stat_name] = stat_value

        return target_hash

    def read_callback(self):
        try:
            start = datetime.datetime.now()
            stats = self.get_stats()
            self.logverbose("collectd new data from service :: took %d seconds"
                    % (datetime.datetime.now() - start).seconds)
        except Exception as exc:
            collectd.error("%s: failed to get stats :: %s :: %s"
                    % (self.prefix, exc, traceback.format_exc()))
        self.dispatch(stats)

    def get_stats(self):
        collectd.error('Not implemented, should be subclassed')

    def logverbose(self, msg):
        if self.verbose:
            collectd.info("%s: %s" % (self.prefix, msg))

    def logdebug(self, msg):
        if self.debug:
            collectd.info("%s: %s" % (self.prefix, msg))

