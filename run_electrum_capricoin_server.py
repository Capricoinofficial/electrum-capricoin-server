#!/usr/bin/env python
# Copyright(C) 2012 thomasv@gitorious

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/agpl.html>.

import argparse
import ConfigParser
import logging
import socket
import sys
import time
import threading
import json
import os
import imp


if os.path.dirname(os.path.realpath(__file__)) == os.getcwd():
    imp.load_module('electrumcapricoinserver', *imp.find_module('src'))

from electrumcapricoinserver import storage, networks, utils
from electrumcapricoinserver.processor import Dispatcher, print_log
from electrumcapricoinserver.server_processor import ServerProcessor
from electrumcapricoinserver.blockchain_processor import BlockchainProcessor
from electrumcapricoinserver.stratum_tcp import TcpServer
from electrumcapricoinserver.stratum_http import HttpServer


logging.basicConfig()

if sys.maxsize <= 2**32:
    print "Warning: it looks like you are using a 32bit system. You may experience crashes caused by mmap"

if os.getuid() == 0:
    print "Do not run this program as root!"
    print "Run the install script to create a non-privileged user."
    sys.exit()

def attempt_read_config(config, filename):
    try:
        with open(filename, 'r') as f:
            config.readfp(f)
    except IOError:
        pass

def load_banner(config):
    try:
        with open(config.get('server', 'banner_file'), 'r') as f:
            config.set('server', 'banner', f.read())
    except IOError:
        pass

def setup_network_params(config):
    type = config.get('network', 'type')
    params = networks.params.get(type)
    utils.PUBKEY_ADDRESS = int(params.get('pubkey_address'))
    utils.SCRIPT_ADDRESS = int(params.get('script_address'))
    storage.GENESIS_HASH = params.get('genesis_hash')

    if config.has_option('network', 'pubkey_address'):
        utils.PUBKEY_ADDRESS = config.getint('network', 'pubkey_address')
    if config.has_option('network', 'script_address'):
        utils.SCRIPT_ADDRESS = config.getint('network', 'script_address')
    if config.has_option('network', 'genesis_hash'):
        storage.GENESIS_HASH = config.get('network', 'genesis_hash')

def create_config(filename=None):
    config = ConfigParser.ConfigParser()
    # set some defaults, which will be overwritten by the config file
    config.add_section('server')
    config.set('server', 'banner', 'Welcome to Capricoin Electrum!')
    config.set('server', 'banner_file', '/etc/electrum-capricoin.banner')
    config.set('server', 'host', 'localhost')
    config.set('server', 'electrum_rpc_port', '8012')
    config.set('server', 'report_host', '')
    config.set('server', 'stratum_tcp_port', '50011')
    config.set('server', 'stratum_http_port', '8091')
    config.set('server', 'stratum_tcp_ssl_port', '50012')
    config.set('server', 'stratum_http_ssl_port', '8092')
    config.set('server', 'report_stratum_tcp_port', '50011')
    config.set('server', 'report_stratum_http_port', '8091')
    config.set('server', 'report_stratum_tcp_ssl_port', '50012')
    config.set('server', 'report_stratum_http_ssl_port', '8092')
    config.set('server', 'ssl_certfile', '')
    config.set('server', 'ssl_keyfile', '')
	
    config.set('server', 'irc', 'no')
    config.set('server', 'irc_nick', '')
    config.set('server', 'coin', 'capricoin')
    config.set('server', 'logfile', '/var/log/electrum-capricoin.log')
    config.set('server', 'donation_address', '')
    config.set('server', 'max_subscriptions', '10000')

    config.add_section('leveldb')
    config.set('leveldb', 'path', '/dev/shm/electrum-capricoin_db')
    config.set('leveldb', 'pruning_limit', '1000')
    config.set('leveldb', 'utxo_cache', str(64*1024*1024))
    config.set('leveldb', 'hist_cache', str(128*1024*1024))
    config.set('leveldb', 'addr_cache', str(16*1024*1024))
    config.set('leveldb', 'profiler', 'no')

    # set network parameters
    config.add_section('network')
    config.set('network', 'type', 'capricoin_main')

    # try to find the config file in the default paths
    if not filename:
        for path in ('/etc/', ''):
            filename = path + 'electrum-capricoin.conf'
            if os.path.isfile(filename):
                break

    if not os.path.isfile(filename):
        print 'could not find electrum configuration file "%s"' % filename
        sys.exit(1)

    attempt_read_config(config, filename)

    load_banner(config)

    return config


def run_rpc_command(params, electrum_rpc_port):
    cmd = params[0]
    import xmlrpclib
    server = xmlrpclib.ServerProxy('http://localhost:%d' % electrum_rpc_port)
    func = getattr(server, cmd)
    r = func(*params[1:])
    if cmd == 'sessions':
        now = time.time()
        print 'type           address         sub  version  time'
        for item in r:
            print '%4s   %21s   %3s  %7s  %.2f' % (item.get('name'),
                                                   item.get('address'),
                                                   item.get('subscriptions'),
                                                   item.get('version'),
                                                   (now - item.get('time')),
                                                   )
    else:
        print json.dumps(r, indent=4, sort_keys=True)


def cmd_banner_update():
    load_banner(dispatcher.shared.config)
    return True

def cmd_getinfo():
    return {
        'blocks': chain_proc.storage.height,
        'peers': len(server_proc.peers),
        'sessions': len(dispatcher.request_dispatcher.get_sessions()),
        'watched': len(chain_proc.watched_addresses),
        'cached': len(chain_proc.history_cache),
        }

def cmd_sessions():
    return map(lambda s: {"time": s.time,
                          "name": s.name,
                          "address": s.address,
                          "version": s.version,
                          "subscriptions": len(s.subscriptions)},
               dispatcher.request_dispatcher.get_sessions())

def cmd_numsessions():
    return len(dispatcher.request_dispatcher.get_sessions())

def cmd_peers():
    return server_proc.peers.keys()

def cmd_numpeers():
    return len(server_proc.peers)

def cmd_debug(s):
    import traceback
    from guppy import hpy; 
    hp = hpy()
    if s:
        try:
            result = str(eval(s))
        except:
            err_lines = traceback.format_exc().splitlines()
            result = '%s | %s' % (err_lines[-3], err_lines[-1])
        return result


def get_port(config, name):
    try:
        return config.getint('server', name)
    except:
        return None


# global
shared = None
chain_proc = None
server_proc = None
dispatcher = None
transports = []

def start_server(config):
    global shared, chain_proc, server_proc, dispatcher

    logfile = config.get('server', 'logfile')
    utils.init_logger(logfile)
    host = config.get('server', 'host')
    stratum_tcp_port = get_port(config, 'stratum_tcp_port')
    stratum_http_port = get_port(config, 'stratum_http_port')
    stratum_tcp_ssl_port = get_port(config, 'stratum_tcp_ssl_port')
    stratum_http_ssl_port = get_port(config, 'stratum_http_ssl_port')
    ssl_certfile = config.get('server', 'ssl_certfile')
    ssl_keyfile = config.get('server', 'ssl_keyfile')

    setup_network_params(config)

    if ssl_certfile is '' or ssl_keyfile is '':
        stratum_tcp_ssl_port = None
        stratum_http_ssl_port = None

    print_log("Starting Electrum server on", host)

    # Create hub
    dispatcher = Dispatcher(config)
    shared = dispatcher.shared

    # handle termination signals
    import signal
    def handler(signum = None, frame = None):
        print_log('Signal handler called with signal', signum)
        shared.stop()
    for sig in [signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT]:
        signal.signal(sig, handler)

    # Create and register processors
    chain_proc = BlockchainProcessor(config, shared)
    dispatcher.register('blockchain', chain_proc)

    server_proc = ServerProcessor(config, shared)
    dispatcher.register('server', server_proc)

    # Create various transports we need
    if stratum_tcp_port:
        tcp_server = TcpServer(dispatcher, host, stratum_tcp_port, False, None, None)
        transports.append(tcp_server)

    if stratum_tcp_ssl_port:
        tcp_server = TcpServer(dispatcher, host, stratum_tcp_ssl_port, True, ssl_certfile, ssl_keyfile)
        transports.append(tcp_server)

    if stratum_http_port:
        http_server = HttpServer(dispatcher, host, stratum_http_port, False, None, None)
        transports.append(http_server)

    if stratum_http_ssl_port:
        http_server = HttpServer(dispatcher, host, stratum_http_ssl_port, True, ssl_certfile, ssl_keyfile)
        transports.append(http_server)

    for server in transports:
        server.start()


def stop_server():
    shared.stop()
    server_proc.join()
    chain_proc.join()
    print_log("Electrum Server stopped")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--conf', metavar='path', default=None, help='specify a configuration file')
    parser.add_argument('command', nargs='*', default=[], help='send a command to the server')
    args = parser.parse_args()
    config = create_config(args.conf)

    electrum_rpc_port = get_port(config, 'electrum_rpc_port')

    if len(args.command) >= 1:
        try:
            run_rpc_command(args.command, electrum_rpc_port)
        except socket.error:
            print "server not running"
            sys.exit(1)
        sys.exit(0)

    try:
        run_rpc_command(['getpid'], electrum_rpc_port)
        is_running = True
    except socket.error:
        is_running = False

    if is_running:
        print "server already running"
        sys.exit(1)

    start_server(config)

    from SimpleXMLRPCServer import SimpleXMLRPCServer
    server = SimpleXMLRPCServer(('localhost', electrum_rpc_port), allow_none=True, logRequests=False)
    server.register_function(lambda: os.getpid(), 'getpid')
    server.register_function(shared.stop, 'stop')
    server.register_function(cmd_getinfo, 'getinfo')
    server.register_function(cmd_sessions, 'sessions')
    server.register_function(cmd_numsessions, 'numsessions')
    server.register_function(cmd_peers, 'peers')
    server.register_function(cmd_numpeers, 'numpeers')
    server.register_function(cmd_debug, 'debug')
    server.register_function(cmd_banner_update, 'banner_update')
    server.socket.settimeout(1)
 
    while not shared.stopped():
        try:
            server.handle_request()
        except socket.timeout:
            continue
        except:
            stop_server()
