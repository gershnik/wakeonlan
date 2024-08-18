# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

"""Yet another wake-on-lan library"""

import sys
import os
import socket
import argparse
import re
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple, Union, Optional

VERSION = '1.3'

PROG = 'wakeonlan'

DESCRIPTION = 'Send Wake-On-Lan packet to a given machine'

USAGE = r'''
%(prog)s MAC [-a IPADDR] [-p PORT]
%(prog)s NAME
%(prog)s --save NAME MAC [-a IPADDR] [-p PORT]
%(prog)s --delete NAME
%(prog)s --list
%(prog)s --names
%(prog)s --autocomplete-source
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
NAMES_CMD           = 6
AUTOC_SOURCE        = 7

MacAddress = Sequence[int]
IPAddress = str
Port = int
SocketAddress = Union[Tuple[Any, ...], str, Any] #see socket._Address
HostRecord = Tuple[MacAddress, Tuple[IPAddress, Port]] 

class WakeOnLanError(Exception):
    """Exception raised when something goes wrong"""
    def __init__(self, message: str):
        super().__init__(message)

def _split_mac(mac: str):
    return [int(x, 16) for x in mac.split(':')]

def _join_mac(mac_items: MacAddress):
    return ':'.join([f'{x:02X}' for x in mac_items])

def _parse_args():

    def mac_address_or_name(string: str):
        if MAC_PATTERN.match(string):
            return _split_mac(string)
        return string
    
    def ip_address(string: str):
        if not IP_PATTERN.match(string):
            raise argparse.ArgumentTypeError('invalid IPv4 address ' + string)
        return string

    def port(string: str):
        try:
            val = int(string)
            if val < 0 or val >= 65535:
                raise argparse.ArgumentTypeError('invalid port ' + string)
            return val
        except ValueError as ex:
            raise argparse.ArgumentTypeError('invalid port ' + string) from ex

    def exit_with_message(parser: argparse.ArgumentParser, message: str):
        print(message, file=sys.stderr)
        parser.print_usage()
        sys.exit(1)

    parser = argparse.ArgumentParser(description=DESCRIPTION, usage=USAGE, add_help=False,
                                     prog=PROG)
    args_group = parser.add_argument_group('arguments')
    args_group.add_argument('mac_or_name', type=mac_address_or_name, nargs='?', metavar='MAC or NAME',
                            help='''MAC address or saved name of the machine to wake. 
                            MAC address must be in XX:XX:XX:XX:XX:XX format''')
    flags_group = parser.add_argument_group('switches')
    flags_group.add_argument('-a', dest='ipaddr', type=ip_address, 
                             help='Broadcast IPv4 address. This is NOT the IP address of the machine')
    flags_group.add_argument('-p', dest='port', type=port, 
                             help='Wake-On-Lan port')
    manage_group = flags_group.add_mutually_exclusive_group()
    manage_group.add_argument('--save', '-s', type=str, dest='save_name', metavar='NAME', 
                              help='Save wake arguments as NAME')
    manage_group.add_argument('--delete', '-d', type=str, dest='delete_name', metavar='NAME', 
                              help='Delete saved NAME')
    manage_group.add_argument('--list', '-l', action='store_true', dest='list_definitions', 
                              help='List saved definitions')
    manage_group.add_argument('--names', '-n', action='store_true', dest='list_names', 
                              help='List saved names')
    manage_group.add_argument('--autocomplete-source', action='store_true', dest='autocomplete_source', 
                              help='Print out path to a script suitable for sourcing into a shell to set up auto-complete')
    flags_group.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    flags_group.add_argument('--help', '-h', action='help',
                             help='show this help message and exit')
    parser.set_defaults(cmd=0)

    args = parser.parse_args()

    if not args.save_name is None:
        if not isinstance(args.mac_or_name, list):
            exit_with_message(parser, 'Must specify MAC address to save')
        args.cmd = SAVE_CMD
    elif not args.delete_name is None:
        if not args.mac_or_name is None:
            exit_with_message(parser, 'parameter MAC_OR_NAME: not allowed with --delete/-d')
        if not args.ipaddr is None:
            exit_with_message(parser, 'argument -a: not allowed with argument with --delete/-d')
        if not args.port is None:
            exit_with_message(parser, 'argument -p: not allowed with argument with --delete/-d')
        args.cmd = DELETE_CMD
    elif args.list_definitions:
        if not args.mac_or_name is None:
            exit_with_message(parser, 'parameter MAC_OR_NAME: not allowed with --list/-l')
        if not args.ipaddr is None:
            exit_with_message(parser, 'argument -a: not allowed with argument with --list/-l')
        if not args.port is None:
            exit_with_message(parser, 'argument -p: not allowed with argument with --list/-l')
        args.cmd = LIST_CMD
    elif args.list_names:
        if not args.mac_or_name is None:
            exit_with_message(parser, 'parameter MAC_OR_NAME: not allowed with --names/-n')
        if not args.ipaddr is None:
            exit_with_message(parser, 'argument -a: not allowed with argument with --names/-n')
        if not args.port is None:
            exit_with_message(parser, 'argument -p: not allowed with argument with --names/-n')
        args.cmd = NAMES_CMD
    elif args.autocomplete_source:
        if not args.mac_or_name is None:
            exit_with_message(parser, 'parameter MAC_OR_NAME: not allowed with --autocomplete-source')
        if not args.ipaddr is None:
            exit_with_message(parser, 'argument -a: not allowed with argument with --autocomplete-source')
        if not args.port is None:
            exit_with_message(parser, 'argument -p: not allowed with argument with --autocomplete-source')
        args.cmd = AUTOC_SOURCE


    if args.cmd == 0:
        if args.mac_or_name is None: # type: ignore
            exit_with_message(parser, 'MAC or name is required')
        if isinstance(args.mac_or_name, list): # type: ignore
            args.cmd = WAKE_CMD
        else:
            if not args.ipaddr is None:
                exit_with_message(parser, 'Cannot specify broadcast address with name')
            if not args.port is None:
                exit_with_message(parser, 'Cannot specify port with name')
            args.cmd = WAKE_BY_NAME_CMD

    if args.cmd == SAVE_CMD or args.cmd == WAKE_CMD:
        args.ipaddr = DEFAULT_IP if args.ipaddr is None else args.ipaddr
        args.port = DEFAULT_PORT if args.port is None else args.port

    return args

def wake(mac: MacAddress, addr: SocketAddress) -> None :
    """wake a machine at a given MAC and IP(v6) address"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    payload = bytearray(17 * 6)
    for i in range(6):
        payload[i] = 0xFF
    for i in range(6, len(payload), 6):
        payload[i:] = mac

    sock.sendto(payload, addr)

def _load_config() -> Dict[Any, Any]:
    try:
        with open(CONFIG_PATH, 'rt', encoding='utf-8') as config:
            config = json.load(config)
            if not isinstance(config, dict):
                raise WakeOnLanError(f'{CONFIG_PATH} is malformed')
            return config # type: ignore
    except json.JSONDecodeError as ex:
        raise WakeOnLanError(f'{CONFIG_PATH} is malformed') from ex
    except OSError:
        pass
    return {'names':{}}

def _save_config(config: Dict[Any, Any]):
    try:
        with open(CONFIG_TMP_PATH, 'wt', encoding='utf-8') as tempfile:
            json.dump(config, tempfile, indent=2)
        shutil.move(CONFIG_TMP_PATH, CONFIG_PATH)
    except OSError as err:
        raise WakeOnLanError(f'Unable to save: {err.strerror}') from err

def _get_names_dict(config: Dict[Any, Any]) -> Dict[Any, Any]:
    names = config.get('names')
    if not isinstance(names, dict):
        raise WakeOnLanError(f'`names` not found in {CONFIG_PATH}')
    return names # type: ignore

def _parse_name_record(name: str, name_record: Dict[Any, Any]) -> HostRecord:
    if not isinstance(name_record, dict): # type: ignore
        raise WakeOnLanError(f'`{name}` entry in {CONFIG_PATH} is malformed')
    mac = name_record.get('mac')
    if not isinstance(mac, str) or not MAC_PATTERN.match(mac):
        raise WakeOnLanError(f'mac address in `{name}` entry in {CONFIG_PATH} is missing or malformed')
    mac = _split_mac(mac)
    ip = name_record.get('ip', DEFAULT_IP)
    if not isinstance(ip, str) or not IP_PATTERN.match(ip):
        raise WakeOnLanError(f'ip address in `{name}` entry in {CONFIG_PATH} is malformed')
    port = name_record.get('port', DEFAULT_PORT)
    if not isinstance(port, int) or port < 0 or port > 65535:
        raise WakeOnLanError(f'port address in `{name}` entry in {CONFIG_PATH} is malformed')
    
    return (mac, (ip, port))

def get_name_record(name: str) -> Optional[HostRecord]:
    """Get stored record"""
    config = _load_config()
    names = _get_names_dict(config)
    name_record = names.get(name)
    if name_record is None:
        return None
    return _parse_name_record(name, name_record)

def get_names() -> Dict[str, HostRecord] :
    """Retrieve all stored records"""
    config = _load_config()
    names = _get_names_dict(config)
    ret: Dict[str, HostRecord] = {}
    for name, name_record in names.items():
        ret[name] = _parse_name_record(name, name_record)
    return ret


def save_name(name: str, mac: MacAddress, ipaddr: IPAddress, port: Port) -> None :
    """Save record"""
    config = _load_config()
    names = _get_names_dict(config)
    record: Dict[str, Any] = {
        'mac': _join_mac(mac)
    }
    if ipaddr != DEFAULT_IP:
        record['ip'] = ipaddr
    if port != DEFAULT_PORT:
        record['port'] = port
    names[name] = record
    _save_config(config)

def delete_name(name: str) -> None :
    """Delete saved record"""
    config = _load_config()
    names = _get_names_dict(config)
    names.pop(name, None)
    _save_config(config)

def main() -> int:
    """script entry point"""
    args = _parse_args()

    try:

        if args.cmd == WAKE_CMD:
            print(f'wake: {args.mac_or_name}, {args.ipaddr}, {args.port}')
            wake(args.mac_or_name, (args.ipaddr, args.port))
        elif args.cmd == WAKE_BY_NAME_CMD:
            name_record = get_name_record(args.mac_or_name)
            if name_record is None:
                raise WakeOnLanError(f'Name {args.mac_or_name} not found')
            mac, addr = name_record
            print(f'wake: {_join_mac(mac)}, {addr[0]}, {addr[1]}')
            wake(mac, addr)
        elif args.cmd == SAVE_CMD:
            save_name(args.save_name, args.mac_or_name, args.ipaddr, args.port)
            print(f'Name {args.save_name} saved')
        elif args.cmd == DELETE_CMD:
            delete_name(args.delete_name)
            print(f'Name {args.delete_name} deleted')
        elif args.cmd == LIST_CMD:
            names = get_names()
            for name, name_record in names.items():
                mac, addr = name_record
                mac = _join_mac(mac)
                print(f'{name} - {mac}, {addr[0]}, {addr[1]}')
        elif args.cmd == NAMES_CMD:
            names = get_names()
            for name in names:
                print(name)
        elif args.cmd == AUTOC_SOURCE:
            if not os.environ.get('PSMODULEPATH') is None:
                print(str(Path(__file__).parent / 'autocomplete.ps1'))
            else:
                print(str(Path(__file__).parent / 'autocomplete.sh'))
        return 0
    except WakeOnLanError as ex:
        print(ex, file=sys.stderr)
        return 1
