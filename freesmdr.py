#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Free SMDR daemon
by Gabriele Tozzi <gabriele@tozzi.eu>, 2010-2011
'''

from ConfigParser import SafeConfigParser
import argparse
from SocketServer import TCPServer
from SocketServer import BaseRequestHandler
import sys, os
from optparse import OptionParser
import traceback
import re, math
from datetime import datetime, time
#import MySQLdb
import logging
import signal
from string import Template

# Info
NAME = 'Free SMDR'
VERSION = '0.9'

# Settings
HOST = ''                     #Listen on this IP
PORT = 5514                   #Listen on this port
LOGFILE = 'freesmdr.log' #Where to log the received data
LOGINFO = 'freesmdr.info' #Debug output
MYSQL_DB = {
    'host': 'localhost',
    'user': 'freesmdr',
    'passwd': '',
    'db': 'freesmdr',
    'table': 'freesmdr',
}

# Classes
class ParserError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class RecvHandler(BaseRequestHandler):

    def handle(self):
        """ Handles established connection
    
        self.request is the socket
        """
        
        global server_running
        global MYSQL_DB
        log = logging.getLogger('req_handler')

        # Init parser
        #parser = re.compile('^(("(?:[^"]|"")*"|[^,]*)(,("(?:[^"]|"")*"|[^,]*))*)$')
        parser = re.compile(',')
        fieldlist = (
            ( "call_start", 'datetime', '%Y/%m/%d %H:%M:%S' ),
            ( "call_duration", 'time', '%H:%M:%S' ),
            ( "ring_duration", 'timeint' ), # In seconds, max 9999
            ( "caller", 'str', 255 ),
            ( "direction", 'enum', ['I','O'] ), #Inbound, Outbound
            ( "called_number", 'str', 255 ),
            ( "dialled_number", 'str', 255 ),
            ( "account", 'str', 255 ),
            ( "is_internal", 'bool' ), #0 or 1
            ( "call_id", 'int' ), #Internal avaya call ID
            ( "continuation", 'bool' ), #Tells if there is a further record for this callID
            ( "party1device", 'str', 5 ), #(E|T|V)xxx E=Extension, T=Trunk, V=voicemail
            ( "party1name", 'str', 255 ),
            ( "party2device", 'str', 5 ), #Like above
            ( "party2name", 'str', 255 ),
            ( "hold_time", 'timeint' ), #Seconds
            ( "park_time", 'timeint' ), #Seconds
            ( "authvalid", 'str', 255 ), #Undocumented from here
            ( "authcode", 'str', 255 ),
            ( "user_charged", 'str', 255 ),
            ( "call_charge", 'str', 255 ),
            ( "currency", 'str', 255 ),
            ( "amount_change", 'str', 255 ),
            ( "call_units", 'str', 255 ),
            ( "units_change", 'str', 255 ),
            ( "cost_per_unit", 'str', 255 ),
            ( "markup", 'str', 255 ),
        );

        peerinfo = self.request.getpeername()
        log.info(u'Got connection from ' + unicode(peerinfo[0]) + ' (' + unicode(peerinfo[1]) + ')')
        

        #Receive data loop
        dbuffer = ""
        while server_running:
            data = self.request.recv(1024)
            if not data:
                break

            # Append data to LOGFILE
            lgf = open(LOGFILE, 'ab')
            lgf.write(data)
            lgf.close()

            # Process data
            line = data.strip(" \n\r\t")
            vals = parser.split(line)
            if len(vals) >= len(fieldlist):
                # Received a good line
                # Build a dictionary
                dictv = {}
                i = 0
                try:
                    for v in fieldlist:
                        if v[1] == 'datetime':
                            dictv[v[0]] = datetime.strptime(vals[i], v[2])
                        elif v[1] == 'time':
                            dictv[v[0]] = datetime.strptime(vals[i], v[2]).time()
                        elif v[1] == 'timeint':
                            z = int(vals[i])
                            h = int(math.floor( z / ( 60 ** 2 ) ))
                            m = int(math.floor( ( z - ( h * 60 ** 2 ) ) / 60 ** 1 ))
                            s = z - ( h * 60 ** 2 ) - ( m * 60 ** 1 )
                            dictv[v[0]] = time(h, m, s)
                        elif v[1] == 'int':
                            dictv[v[0]] = int(vals[i])
                        elif v[1] == 'str':
                            if len(vals[i]) > v[2]:
                                raise ParserError(v[0] + ': String too long')
                            dictv[v[0]] = str(vals[i])
                        elif v[1] == 'bool':
                            if vals[i] != '0' and vals[i] != '1':
                                raise ParserError(v[0] + ': Unvalid boolean')
                            dictv[v[0]] = bool(vals[i])
                        elif v[1] == 'enum':
                            if not vals[i] in v[2]:
                                raise ParserError(v[0] + ': Value out of range')
                            dictv[v[0]] = str(vals[i])
                        else:
                            raise ParserError(v[0] + ': Unknown field type ' + v[1])
                        i += 1
                
                except Exception, e:
                    # Unable to parse line
                    log.error(u"Parse error on line (" + str(v[0]) + str(vals[i]) + "): got exception " + unicode(e) + " (" + str(line) + ")")
                
                else:
                    # Line parsed correctly
                    log.debug(u"Correctly parsed 1 line: " + unicode(dictv))
                    
                    #Prepare dictv for query
                    #map(lambda v: MySQLdb.string_literal(v), dictv)
                    dictv['table'] = MYSQL_DB['table']
                    
                    # Put the data into the DB
                    #cursor = conn.cursor()
                    #q = """
                    #    INSERT INTO `%(table)s` SET
                    #        `call_start` = '%(call_start)s',
                    #        `call_duration` = '%(call_duration)s',
                    #        `ring_duration` = '%(ring_duration)s',
                    #        `caller` = '%(caller)s',
                    #        `direction` = '%(direction)s',
                    #        `called_number` = '%(called_number)s',
                    #        `dialled_number` = '%(dialled_number)s',
                    #        `account` = '%(account)s',
                    #        `is_internal` = %(is_internal)d,
                    #        `call_id` = %(call_id)d,
                    #        `continuation` = %(continuation)d,
                    #        `paty1device` = '%(party1device)s',
                    #        `party1name` = '%(party1name)s',
                    #        `party2device` = '%(party2device)s',
                    #        `party2name` = '%(party2name)s',
                    #        `hold_time` = '%(hold_time)s',
                    #        `park_time` = '%(park_time)s',
                    #        `authvalid` = '%(authvalid)s',
                    #        `authcode` = '%(authcode)s',
                    #        `user_charged` = '%(user_charged)s',
                    #        `call_charge` = '%(call_charge)s',
                    #        `currency` = '%(currency)s',
                    #        `amount_change` = '%(amount_change)s',
                    #        `call_units` = '%(call_units)s',
                    #        `units_change` = '%(units_change)s',
                    #        `cost_per_unit` = '%(cost_per_unit)s',
                    #        `markup` = '%(markup)s';
                    #""" % dictv
                    log.info(unicode(dictv))
                    template = Template("$call_start, $call_duration, $ring_duration, $caller, $direction, $called_number, $dialled_number, $account, $is_internal, $call_id, $continuation, $party1device, $party1name, $party2device, $party2name, $hold_time, $park_time, $authvalid, $authcode, $user_charged, $call_charge, $currency, $amount_change, $call_units, $units_change, $cost_per_unit, $markup,")
                    q = template.substitute(call_start= dictv['call_start'],
                                            call_duration= dictv['call_duration'],
                                            ring_duration= dictv['ring_duration'],
                                            caller= dictv['caller'],
                                            direction= dictv['direction'],
                                            called_number= dictv['called_number'],
                                            dialled_number= dictv['dialled_number'],
                                            account= dictv['account'],
                                            is_internal= dictv['is_internal'],
                                            call_id= dictv['call_id'],
                                            continuation= dictv['continuation'],
                                            party1device= dictv['party1device'],
                                            party1name= dictv['party1name'],
                                            party2device= dictv['party2device'],
                                            party2name= dictv['party2name'],
                                            hold_time= dictv['hold_time'],
                                            park_time= dictv['park_time'],
                                            authvalid= dictv['authvalid'],
                                            authcode= dictv['authcode'],
                                            user_charged= dictv['user_charged'],
                                            call_charge= dictv['call_charge'],
                                            currency= dictv['currency'],
                                            amount_change= dictv['amount_change'],
                                            call_units= dictv['call_units'],
                                            units_change= dictv['units_change'],
                                            cost_per_unit= dictv['cost_per_unit'],
                                            markup= dictv['markup'])

                    log.debug(u"Query: " + unicode(q))
                    log.info(unicode(q))
                    #cursor.execute(q)
                    #cursor.close()
            
            else:
                log.error(u"Parse error on line (len " + str(len(vals)) + " vs " + str(len(fieldlist)) + "): " + unicode(line))


        # Connection terminated
        log.info(unicode(peerinfo[0]) + ' (' + unicode(peerinfo[1]) + ') disconnected')


def exitcleanup(signum):
    print "Signal %s received, exiting..." % signum
    server.server_close()
    sys.exit(0)

def sighandler(signum = None, frame = None):
    exitcleanup(signum)

def parse_args():
    usage = "%prog [options]"
    parser = OptionParser(usage=usage, version=NAME + ' ' + VERSION)
    parser.add_option("-c", "--config", dest="config",
                help="config file path", action="store")
    parser.add_option("-f", "--foreground", dest="foreground",
                help="don't daemonize", action="store_true")
    return parser.parse_args()

def parse_config(file_path):
    parser = SafeConfigParser()
    parser.read(file_path)

    core = {}
    core['host'] = parser.get('core', 'host')
    core['port'] = parser.get('core', 'port')

    logger = {}
    logger['level'] = parser.get('logger', 'level')
    logger['file']  = parser.get('logger', 'file')
    logger['debug'] = parser.get('logger', 'debug')

    mysql = {}
    mysql['host']     = parser.get('mysql', 'host')
    mysql['user']     = parser.get('mysql', 'user')
    mysql['password'] = parser.get('mysql', 'password')
    mysql['db']       = parser.get('mysql', 'db')
    mysql['table']    = parser.get('mysql', 'table')

    elasticsearch = {}
    elasticsearch['url']   = parser.get('elasticsearch', 'url')
    elasticsearch['port']  = parser.get('elasticsearch', 'port')
    elasticsearch['index'] = parser.get('elasticsearch', 'index')

    return (core, logger, mysql, elasticsearch)


def daemonize():
    pid = os.fork()

if __name__=="__main__":
    # Parse command line
    (options, args) = parse_args()

    (core, logger, mysql, elasticsearch) = parse_config(options.config)

    # Gracefully process signals
    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGINT, sighandler)

    # Fork & go to background
    if not options.foreground:
        # daemonize
        pid = os.fork()
    else:
        pid = 0
    if pid == 0:
        # 1st child
        if not options.foreground:
            os.setsid()
            pid = os.fork()
        if pid == 0:
            # 2nd child
            # Set up file logging
            if logger['level'] == "DEBUG":
                log_level = logging.DEBUG
            else:
                log_level = logging.INFO

            logging.basicConfig(
                level = log_level,
                format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                datefmt = '%Y-%m-%d %H:%M:%S',
                filename = logger['debug'],
                filemode = 'a'
            )

            if options.foreground:
                # Set up console logging
                console = logging.StreamHandler()
                console.setLevel(logging.INFO)
                formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
                console.setFormatter(formatter)
                logging.getLogger('').addHandler(console)

            # Create logger
            log = logging.getLogger()

            # Start server
            server_running = True
            server = TCPServer((HOST, PORT), RecvHandler)
            try:
                server.serve_forever()
            except Exception as e:
                log.critical("Got exception, crashing...")
                log.critical(unicode(e))
                log.critical(traceback.format_exc())
                raise e
            server.server_close()
            sys.exit(0)
        else:
            os._exit(0)
    else:
        os._exit(0)
