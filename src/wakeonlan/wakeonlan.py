# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

import sys
import os
import socket
import argparse
import re
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple, Union

VERSION = '1.1'

PROG = 'wakeonlan'

DESCRIPTION = 'Send Wake-On-Lan packet to a given machine'

USAGE = r'''
%(prog)s MAC [-a IPADDR] [-p PORT]
%(prog)s NAME
%(prog)s --save NAME MAC [-a IPADDR] [-p PORT]
%(prog)s --delete NAME
%(prog)s --list
%(prog)s --version
%(prog)s --help
'''


DEFAULT_IP = '255.255.255.255'
DEFAULT_PORT = 9
CONFIG_HOME = Path(os.environ.get('WAKEONLAN_HOME', Path.home()))
CONFIG_PATH = CONFIG_HOME / '.wakeonlan'
CONFIG_TMP_PATH = CONFIG_HOME /'.wakeonlan.tmp'
MAC_PATTERN = re.compile(r'[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}')
IP_PATTERN = re.compile(r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')
     

WAKE_CMD            = 1
WAKE_BY_NAME_CMD    = 2
SAVE_CMD            = 3
DELETE_CMD          = 4
LIST_CMD            = 5

MacAddress = Sequence[int]
IPAddress = str
Port = int
SocketAddress = Union[Tuple[Any, ...], str, Any] #see socket._Address
HostRecord = Tuple[MacAddress, Tuple[IPAddress, Port]] 

class WakeOnLanError(Exception):
    def __init__(self, message):
        super().__init__(message)

def splitMac(mac):
    return [int(x, 16) for x in mac.split(':')]

def joinMac(macItems):
    return ':'.join([f'{x:02X}' for x in macItems])

def parseArgs():

    def mac_address_or_name(string):
        if MAC_PATTERN.match(string):
            return splitMac(string)
        return string
    
    def ip_address(string):
        if not IP_PATTERN.match(string):
            raise argparse.ArgumentTypeError('invalid IPv4 address ' + string)
        return string

    def port(string):
        try:
            val = int(string)
            if val < 0 or val >= 65535:
                raise argparse.ArgumentTypeError('invalid port ' + string)
            return val
        except ValueError:
            raise argparse.ArgumentTypeError('invalid port ' + string)

    def exitWithMessage(parser, message):
        print(message, file=sys.stderr)
        parser.print_usage()
        sys.exit(1)

    parser = argparse.ArgumentParser(description=DESCRIPTION, usage=USAGE, add_help=False,
                                     prog=PROG)
    argsGroup = parser.add_argument_group('arguments')
    argsGroup.add_argument('macOrName', type=mac_address_or_name, nargs='?', metavar='MAC or NAME',
                            help='''MAC address or saved name of the machine to wake. 
                            MAC address must be in XX:XX:XX:XX:XX:XX format''')
    flagsGroup = parser.add_argument_group('switches')
    flagsGroup.add_argument('-a', dest='ipaddr', type=ip_address, 
                            help='Broadcast IPv4 address. This is NOT the IP address of the machine')
    flagsGroup.add_argument('-p', dest='port', type=port, 
                            help='Wake-On-Lan port')
    manageGroud = flagsGroup.add_mutually_exclusive_group()
    manageGroud.add_argument('--save', '-s', type=str, dest='saveName', metavar='NAME', 
                             help='Save wake arguments as NAME')
    manageGroud.add_argument('--delete', '-d', type=str, dest='deleteName', metavar='NAME', 
                             help='Delete saved NAME')
    manageGroud.add_argument('--list', '-l', action='store_true', dest='listNames', 
                             help='List saved names')
    flagsGroup.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    flagsGroup.add_argument('--help', '-h', action='help',
                            help='show this help message and exit')
    parser.set_defaults(cmd=0)

    args = parser.parse_args()

    if not args.saveName is None:
        if not type(args.macOrName) is list:
            exitWithMessage(parser, 'Must specify MAC address to save')
        args.cmd = SAVE_CMD
    elif not args.deleteName is None:
        if not args.macOrName is None:
            exitWithMessage(parser, 'parameter MAC_OR_NAME: not allowed with --delete/-d')
        if not args.ipaddr is None:
            exitWithMessage(parser, 'argument -a: not allowed with argument with --delete/-d')
        if not args.port is None:
            exitWithMessage(parser, 'argument -p: not allowed with argument with --delete/-d')
        args.cmd = DELETE_CMD
    elif args.listNames:
        if not args.macOrName is None:
            exitWithMessage(parser, 'parameter MAC_OR_NAME: not allowed with --list/-l')
        if not args.ipaddr is None:
            exitWithMessage(parser, 'argument -a: not allowed with argument with --list/-l')
        if not args.port is None:
            exitWithMessage(parser, 'argument -p: not allowed with argument with --list/-l')
        args.cmd = LIST_CMD

    if args.cmd == 0:
        if args.macOrName is None:
            exitWithMessage(parser, 'MAC or name is required')
        if type(args.macOrName) is list:
            args.cmd = WAKE_CMD
        else:
            if not args.ipaddr is None:
                exitWithMessage(parser, 'Cannot specify broadcast address with name')
            if not args.port is None:
                exitWithMessage(parser, 'Cannot specify port with name')
            args.cmd = WAKE_BY_NAME_CMD

    if args.cmd == SAVE_CMD or args.cmd == WAKE_CMD:
        args.ipaddr = DEFAULT_IP if args.ipaddr is None else args.ipaddr
        args.port = DEFAULT_PORT if args.port is None else args.port

    return args

def wake(mac: MacAddress, addr: SocketAddress) -> None :
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    payload = bytearray(17 * 6)
    for i in range(6):
        payload[i] = 0xFF
    for i in range(6, len(payload), 6):
        payload[i:] = mac

    sock.sendto(payload, addr)

def loadConfig():
    try:
        with open(CONFIG_PATH, 'rt') as config:
            config = json.load(config)
            if type(config) != dict:
                raise WakeOnLanError(f'{CONFIG_PATH} is malformed')
            return config
    except json.JSONDecodeError:
        raise WakeOnLanError(f'{CONFIG_PATH} is malformed')
    except OSError:
        pass
    return {'names':{}}

def saveConfig(config):
    try:
        with open(CONFIG_TMP_PATH, 'wt') as tempfile:
            json.dump(config, tempfile, indent=2)
        shutil.move(CONFIG_TMP_PATH, CONFIG_PATH)
    except OSError as err:
        raise WakeOnLanError(f'Unable to save: {err.strerror}')

def getNamesDict(config):
    names = config.get('names')
    if type(names) != dict:
        raise WakeOnLanError(f'`names` not found in {CONFIG_PATH}')
    return names

def parseNameRecord(name, nameRecord):
    if type(nameRecord) != dict:
        raise WakeOnLanError(f'`{name}` entry in {CONFIG_PATH} is malformed')
    mac = nameRecord.get('mac')
    if type(mac) != str or not MAC_PATTERN.match(mac):
        raise WakeOnLanError(f'mac address in `{name}` entry in {CONFIG_PATH} is missing or malformed')
    mac = splitMac(mac)
    ip = nameRecord.get('ip', DEFAULT_IP)
    if type(ip) != str or not IP_PATTERN.match(ip):
        raise WakeOnLanError(f'ip address in `{name}` entry in {CONFIG_PATH} is malformed')
    port = nameRecord.get('port', DEFAULT_PORT)
    if type(port) != int or port < 0 or port > 65535:
        raise WakeOnLanError(f'port address in `{name}` entry in {CONFIG_PATH} is malformed')
    
    return (mac, (ip, port))

def getNameRecord(name: str) -> Union[HostRecord, None]:
    config = loadConfig()
    names = getNamesDict(config)
    nameRecord = names.get(name)
    if nameRecord is None:
        return None
    return parseNameRecord(name, nameRecord)

def getNames() -> Dict[str, HostRecord] :
    config = loadConfig()
    names = getNamesDict(config)
    ret = {}
    for name, nameRecord in names.items():
        ret[name] = parseNameRecord(name, nameRecord)
    return ret


def saveName(name: str, mac: MacAddress, ipaddr: IPAddress, port: Port) -> None :
    config = loadConfig()
    names = getNamesDict(config)
    record: Dict[str, Any] = {
        'mac': joinMac(mac)
    }
    if ipaddr != DEFAULT_IP:
        record['ip'] = ipaddr
    if port != DEFAULT_PORT:
        record['port'] = port
    names[name] = record
    saveConfig(config)

def deleteName(name: str) -> None :
    config = loadConfig()
    names = getNamesDict(config)
    names.pop(name, None)
    saveConfig(config)

def main():
    args = parseArgs()

    try:

        if args.cmd == WAKE_CMD:
            print(f'wake: {args.macOrName}, {args.ipaddr}, {args.port}')
            wake(args.macOrName, (args.ipaddr, args.port))
        elif args.cmd == WAKE_BY_NAME_CMD:
            nameRecord = getNameRecord(args.macOrName)
            if nameRecord is None:
                raise WakeOnLanError(f'Name {args.macOrName} not found')
            mac, addr = nameRecord
            print(f'wake: {joinMac(mac)}, {addr[0]}, {addr[1]}')
            wake(mac, addr)
        elif args.cmd == SAVE_CMD:
            saveName(args.saveName, args.macOrName, args.ipaddr, args.port)
            print(f'Name {args.saveName} saved')
        elif args.cmd == DELETE_CMD:
            deleteName(args.deleteName)
            print(f'Name {args.deleteName} deleted')
        elif args.cmd == LIST_CMD:
            names = getNames()
            for name, nameRecord in names.items():
                mac, addr = nameRecord
                mac = joinMac(mac)
                print(f'{name} - {mac}, {addr[0]}, {addr[1]}')
        return 0
    except WakeOnLanError as ex:
        print(ex, file=sys.stderr)
        return 1
