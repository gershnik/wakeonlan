# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

"""Yet another wake-on-lan library"""

import sys
import os
import socket
import re
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple, Union, Optional, NamedTuple

from .util import WakeOnLanError, print_error, print_warning
from .interfaces import enum_interfaces, InterfaceAddress

VERSION = '1.3'

PROG = 'wakeonlan'

DESCRIPTION = 'Send Wake-On-Lan packet to a given machine'

USAGE = r'''
%(prog)s MAC [-i INTERFACE_NAME] [-p PORT]
%(prog)s NAME
%(prog)s --save NAME MAC [-i INTERFACE_NAME] [-p PORT]
%(prog)s --delete NAME
%(prog)s --list
%(prog)s --names
%(prog)s --interfaces
%(prog)s --autocomplete-source
%(prog)s --version
%(prog)s --help
'''


DEFAULT_IP = '255.255.255.255'
DEFAULT_IP6 = 'ff02::1'
DEFAULT_PORT = 9
CONFIG_HOME = Path(os.environ.get('WAKEONLAN_HOME', Path.home()))
CONFIG_PATH = CONFIG_HOME / '.wakeonlan'
MAC_PATTERN = re.compile(r'[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}')
IP_PATTERN = re.compile(r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')
     

WAKE_CMD            = 1
WAKE_BY_NAME_CMD    = 2
SAVE_CMD            = 3
DELETE_CMD          = 4
LIST_CMD            = 5
NAMES_CMD           = 6
IFACES_CMD          = 7
AUTOC_SOURCE        = 8

MacAddress = Tuple[int,int,int,int,int,int]
IPAddress = str
Port = int
SocketAddress = Union[Tuple[Any, ...], str, Any] #see socket._Address

class HostRecord(NamedTuple):
    """Information about how to wake up a given host"""
    mac: MacAddress
    interface: Optional[str]
    address: Optional[IPAddress]
    port: Port

    def mac_str(self):
        """MAC address in a string form"""
        return ':'.join([f'{x:02X}' for x in self.mac])

    def interface_name(self):
        """Interface name sutiable for display to the user"""
        return self.interface if self.interface is not None else self.address if self.address is not None else '*'


def _split_mac(mac: str) -> MacAddress:
    ret = tuple(int(x, 16) for x in mac.split(':'))
    assert len(ret) == 6
    return ret

def _parse_args():
    import argparse

    def mac_address_or_name(string: str):
        if MAC_PATTERN.fullmatch(string):
            return _split_mac(string)
        return string
    
    def ip_address(string: str):
        if not IP_PATTERN.fullmatch(string):
            raise argparse.ArgumentTypeError('invalid IPv4 address ' + string)
        return string

    def port(string: str):
        try:
            val = int(string)
            if val < 0 or val > 65535:
                raise argparse.ArgumentTypeError('invalid port ' + string)
            return val
        except ValueError as ex:
            raise argparse.ArgumentTypeError('invalid port ' + string) from ex

    def exit_with_message(parser: argparse.ArgumentParser, message: str):
        print_error(message)
        parser.print_usage()
        sys.exit(1)

    parser = argparse.ArgumentParser(description=DESCRIPTION, usage=USAGE, add_help=False,
                                     prog=PROG)
    args_group = parser.add_argument_group('arguments')
    args_group.add_argument('mac_or_name', type=mac_address_or_name, nargs='?', metavar='MAC or NAME',
                            help='''MAC address or saved name of the machine to wake. 
                            MAC address must be in XX:XX:XX:XX:XX:XX format''')
    flags_group = parser.add_argument_group('switches')
    flags_group.add_argument('-i', dest='interface', type=str, metavar='INTERFACE_NAME',
                             help='Network interface to send from. If omitted, the wake request is sent on all valid interfaces')
    flags_group.add_argument('-a', dest='ipaddr', type=ip_address, 
                             help='Deprecated, prefer the -i switch. Broadcast IPv4 address of the interface to use. (This is NOT the IP address of the machine you want to wake!)')
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
    manage_group.add_argument('--interfaces', action='store_true', dest='list_interfaces', 
                              help='List valid interfaces')
    manage_group.add_argument('--autocomplete-source', action='store_true', dest='autocomplete_source', 
                              help='Print out path to a script suitable for sourcing into a shell to set up auto-complete')
    flags_group.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    flags_group.add_argument('--help', '-h', action='help',
                             help='show this help message and exit')
    parser.set_defaults(cmd=0)

    args = parser.parse_args()

    if args.save_name is not None:
        if not isinstance(args.mac_or_name, tuple):
            exit_with_message(parser, 'Must specify MAC address to save')
        args.cmd = SAVE_CMD
    else:
        noopt_args = (
            (args.delete_name is not None, '--delete/-d', DELETE_CMD),
            (args.list_definitions, '--list/-l', LIST_CMD),
            (args.list_names, '--names/-n', NAMES_CMD),
            (args.list_interfaces, '--interfaces', IFACES_CMD),
            (args.autocomplete_source, '--autocomplete-source', AUTOC_SOURCE)
        )
        for test, desc, cmd in noopt_args:
            if test:
                if args.mac_or_name is not None:
                    exit_with_message(parser, f'parameter MAC_OR_NAME: not allowed with {desc}')
                if args.interface is not None:
                    exit_with_message(parser, f'argument -i: not allowed with {desc}')
                if args.ipaddr is not None:
                    exit_with_message(parser, f'argument -a: not allowed with argument with {desc}')
                if args.port is not None:
                    exit_with_message(parser, f'argument -p: not allowed with argument with {desc}')
                args.cmd = cmd
                break


    if args.cmd == 0:
        if args.mac_or_name is None: 
            exit_with_message(parser, 'MAC or name is required')
        if isinstance(args.mac_or_name, tuple): 
            args.cmd = WAKE_CMD
        else:
            if args.interface is not None:
                exit_with_message(parser, 'Cannot specify interface with name')
            if args.ipaddr is not None:
                exit_with_message(parser, 'Cannot specify broadcast address with name')
            if args.port is not None:
                exit_with_message(parser, 'Cannot specify port with name')
            args.cmd = WAKE_BY_NAME_CMD

    if args.ipaddr is not None:
        if args.interface is not None:
            exit_with_message(parser, 'Cannot specify both interface and broadcast address')
        print_warning('-a option is deprecated')

    if args.cmd == SAVE_CMD or args.cmd == WAKE_CMD:
        args.port = DEFAULT_PORT if args.port is None else args.port

    return args


def _select_address(addresses: Sequence[InterfaceAddress]) ->Optional[InterfaceAddress]:
    selected: Optional[InterfaceAddress] = None
    for idx, family, addr in addresses:
        if family == socket.AF_INET:
            selected = (idx, family, addr)
            break

    if selected is None:
        for idx, family, addr in addresses:
            if family == socket.AF_INET6:
                selected = (idx, family, addr)
                break
    
    return selected

def _payload(mac: MacAddress):
    payload = bytearray(17 * 6)
    for i in range(6):
        payload[i] = 0xFF
    for i in range(6, len(payload), 6):
        payload[i:i+6] = mac
    return payload

def _wake_with_dest(mac: MacAddress, addr: SocketAddress) -> None :
    """wake a machine at a given MAC and IP(v6) address"""
    
    payload = _payload(mac)

    host, port = addr
    family, socktype, proto, _, sockaddr = socket.getaddrinfo(
        host, port, type=socket.SOCK_DGRAM)[0]
    with socket.socket(family, socktype, proto) as sock:
        if family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(payload, sockaddr)

def _wake_on_interface(mac: MacAddress, address: InterfaceAddress, port: int):
    """wake a machine at a given MAC using a given interface"""

    payload = _payload(mac)

    idx, family, addr = address

    with socket.socket(family, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        if family == socket.AF_INET:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((addr, 0))
            sock.sendto(payload, (DEFAULT_IP, port))
        else:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, idx)
            sock.sendto(payload, (DEFAULT_IP6, port))


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
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=CONFIG_HOME, mode='wt', encoding='utf-8', delete=False) as f:
            tmp_path = f.name
            json.dump(config, f, indent=2)
        os.replace(tmp_path, CONFIG_PATH)
        tmp_path = None
    except OSError as err:
        raise WakeOnLanError(f'Unable to save: {err.strerror}') from err
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

def _get_names_dict(config: Dict[Any, Any]) -> Dict[Any, Any]:
    names = config.get('names')
    if not isinstance(names, dict):
        raise WakeOnLanError(f'`names` not found in {CONFIG_PATH}')
    return names # type: ignore

def _parse_name_record(name: str, name_record: Dict[Any, Any]) -> HostRecord:
    if not isinstance(name_record, dict): 
        raise WakeOnLanError(f'`{name}` entry in {CONFIG_PATH} is malformed')
    mac = name_record.get('mac')
    if not isinstance(mac, str) or not MAC_PATTERN.fullmatch(mac):
        raise WakeOnLanError(f'mac address in `{name}` entry in {CONFIG_PATH} is missing or malformed')
    mac = _split_mac(mac)
    ip = name_record.get('ip', DEFAULT_IP)
    if not isinstance(ip, str) or not IP_PATTERN.fullmatch(ip):
        raise WakeOnLanError(f'ip address in `{name}` entry in {CONFIG_PATH} is malformed')
    if ip == DEFAULT_IP:
        ip = None
    iface = name_record.get('interface')
    if iface is not None:
        if not isinstance(iface, str) or not iface:
            raise WakeOnLanError(f'interface in `{name}` entry in {CONFIG_PATH} is malformed')
        ip = None
    port = name_record.get('port', DEFAULT_PORT)
    if not isinstance(port, int) or port < 0 or port > 65535:
        raise WakeOnLanError(f'port address in `{name}` entry in {CONFIG_PATH} is malformed')
    
    return HostRecord(mac, iface, ip, port)

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


def save_name(name: str, host_record: HostRecord) -> None :
    """Save record"""
    config = _load_config()
    names = _get_names_dict(config)
    record: Dict[str, Any] = {
        'mac': host_record.mac_str()
    }
    if host_record.interface is not None:
        record['interface'] = host_record.interface
    elif host_record.address is not None and host_record.address != DEFAULT_IP:
        record['ip'] = host_record.address
    if host_record.port != DEFAULT_PORT:
        record['port'] = host_record.port
    names[name] = record
    _save_config(config)

def delete_name(name: str) -> None :
    """Delete saved record"""
    config = _load_config()
    names = _get_names_dict(config)
    names.pop(name, None)
    _save_config(config)


def wake(record: HostRecord):
    """wake the entry given by the record"""
    mac, iface, ipaddr, port = record
    ifaces = enum_interfaces()
    if iface is not None:
        src = ifaces.get(iface)
        if src is None:
            raise WakeOnLanError(f'Interface `{iface}` not found or has no usable addresses')
        address = _select_address(src)
        if address is None:
            raise WakeOnLanError(f'Interface `{iface}` has no usable IPv4 or IPv6 address')
        print(f'wake: {record.mac_str()}, {iface}, {port}')
        try:
            _wake_on_interface(mac, address, port)
        except OSError as ex:
            print_error(f'sending failed: {ex}')
    elif ipaddr is not None:
        print(f'wake: {record.mac_str()}, {ipaddr}, {port}')
        try:
            _wake_with_dest(mac, (ipaddr, port))
        except OSError as ex:
            print_error(f'sending failed: {ex}')
    else:
        print(f'wake: {record.mac_str()}, all valid interfaces, {port}')
        errors = {}
        for name, src in ifaces.items():
            address = _select_address(src)
            if address is None:
                continue
            try:
                _wake_on_interface(mac, address, port)
            except OSError as ex:
                errors[name] = ex
        for name, error in errors.items():
            print_error(f'sending on {name} failed: {error}')

def main() -> int:
    """script entry point"""
    args = _parse_args()

    try:

        if args.cmd == WAKE_CMD:
            wake(HostRecord(args.mac_or_name, args.interface, args.ipaddr, args.port))
        elif args.cmd == WAKE_BY_NAME_CMD:
            name_record = get_name_record(args.mac_or_name)
            if name_record is None:
                raise WakeOnLanError(f'Name {args.mac_or_name} not found')
            wake(name_record)
        elif args.cmd == SAVE_CMD:
            save_name(args.save_name, HostRecord(args.mac_or_name, args.interface, args.ipaddr, args.port))
            print(f'Name {args.save_name} saved')
        elif args.cmd == DELETE_CMD:
            delete_name(args.delete_name)
            print(f'Name {args.delete_name} deleted')
        elif args.cmd == LIST_CMD:
            names = get_names()
            for name, name_record in names.items():
                print(f'{name} - {name_record.mac_str()}, {name_record.interface_name()}, {name_record.port}')
        elif args.cmd == NAMES_CMD:
            names = get_names()
            for name in names:
                print(name)
        elif args.cmd == IFACES_CMD:
            ifaces = enum_interfaces()
            for iface in ifaces:
                print(iface)
        elif args.cmd == AUTOC_SOURCE:
            if not os.environ.get('PSMODULEPATH') is None:
                print(str(Path(__file__).parent / 'autocomplete.ps1'))
            else:
                print(str(Path(__file__).parent / 'autocomplete.sh'))
        return 0
    except WakeOnLanError as ex:
        print_error(str(ex))
        return 1
