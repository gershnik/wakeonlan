# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

"""Enumerate network interfaces usable for Wake-On-Lan.

The single public function `enum_interfaces` returns a mapping of interface
name to a list of ``(index, family, address)`` tuples, where `address` is the
interface's own IPv4 or IPv6 address as text.

Filtering rules:

* loopback interfaces are excluded;
* interfaces that don't support multicast are excluded;
* interfaces that aren't currently up are excluded (sending out them would
  fail anyway);
* for IPv6, only link-local addresses (``fe80::/10``) are returned -- those
  are the addresses relevant for link-scoped multicast like ``ff02::1``.
"""

import sys
import os
import ctypes
import ctypes.util
import socket
from typing import Dict, List, Tuple

# (interface index, address family, textual address)
InterfaceAddress = Tuple[int, int, str]


# --------------------------------------------------------------------------- #
# Common helpers
# --------------------------------------------------------------------------- #

def _is_v6_link_local(addr_bytes: bytes) -> bool:
    """Test whether 16-byte IPv6 address falls in ``fe80::/10``."""
    return addr_bytes[0] == 0xFE and (addr_bytes[1] & 0xC0) == 0x80


def _clean_v6_link_local(addr_bytes: bytes) -> bytes:
    """Strip the embedded scope id Linux stuffs into bytes 2-3 of link-local
    addresses returned by getifaddrs. On other platforms those bytes are
    already zero, so this is a no-op there.
    """
    if _is_v6_link_local(addr_bytes):
        return addr_bytes[:2] + b'\x00\x00' + addr_bytes[4:]
    return addr_bytes


# --------------------------------------------------------------------------- #
# Unix: getifaddrs(3)
# --------------------------------------------------------------------------- #


# IFF_* values that can differ across kernels.
_IFF_UP = 0x1
_IFF_LOOPBACK = 0x8

if sys.platform == 'darwin' or 'bsd' in sys.platform or sys.platform.startswith('haiku') or sys.platform.startswith('hp-ux'):
    _IFF_MULTICAST = 0x8000
elif sys.platform.startswith('sunos'):
    _IFF_MULTICAST = 0x800
elif sys.platform.startswith('aix'):
    _IFF_MULTICAST = 0x80000
else:                                      # Linux and other glibc-likes
    _IFF_MULTICAST = 0x1000

if sys.platform == 'darwin' \
    or 'bsd' in sys.platform \
    or sys.platform.startswith('aix') \
    or sys.platform.startswith('haiku'):
    
    class _sockaddr(ctypes.Structure):
        _fields_ = [("sa_len", ctypes.c_uint8), ("sa_family", ctypes.c_uint8),
                    ("sa_data", ctypes.c_uint8 * 14)]

    class _sockaddr_in(ctypes.Structure):
        _fields_ = [("sin_len", ctypes.c_uint8), ("sin_family", ctypes.c_uint8),
                    ("sin_port", ctypes.c_uint16), ("sin_addr", ctypes.c_uint8 * 4),
                    ("sin_zero", ctypes.c_uint8 * 8)]

    class _sockaddr_in6(ctypes.Structure):
        _fields_ = [("sin6_len", ctypes.c_uint8), ("sin6_family", ctypes.c_uint8),
                    ("sin6_port", ctypes.c_uint16), ("sin6_flowinfo", ctypes.c_uint32),
                    ("sin6_addr", ctypes.c_uint8 * 16), ("sin6_scope_id", ctypes.c_uint32)]
else:
    
    class _sockaddr(ctypes.Structure):
        _fields_ = [("sa_family", ctypes.c_uint16), ("sa_data", ctypes.c_uint8 * 14)]

    class _sockaddr_in(ctypes.Structure):
        _fields_ = [("sin_family", ctypes.c_uint16), ("sin_port", ctypes.c_uint16),
                    ("sin_addr", ctypes.c_uint8 * 4), ("sin_zero", ctypes.c_uint8 * 8)]

    class _sockaddr_in6(ctypes.Structure):
        _fields_ = [("sin6_family", ctypes.c_uint16), ("sin6_port", ctypes.c_uint16),
                    ("sin6_flowinfo", ctypes.c_uint32), ("sin6_addr", ctypes.c_uint8 * 16),
                    ("sin6_scope_id", ctypes.c_uint32)]


# Solaris/illumos has uint64_t ifa_flags; everywhere else it's unsigned int.
if sys.platform.startswith('sunos'):
    _ifa_flags_t = ctypes.c_uint64
else:
    _ifa_flags_t = ctypes.c_uint

class _ifaddrs(ctypes.Structure):
    pass


_ifaddrs._fields_ = [
    ("ifa_next",      ctypes.POINTER(_ifaddrs)),
    ("ifa_name",      ctypes.c_char_p),
    ("ifa_flags",     _ifa_flags_t),
    ("ifa_addr",      ctypes.POINTER(_sockaddr)),
    ("ifa_netmask",   ctypes.POINTER(_sockaddr)),
    ("ifa_broadaddr", ctypes.POINTER(_sockaddr)),
    ("ifa_data",      ctypes.c_void_p),
]


def _enum_unix() -> Dict[str, List[InterfaceAddress]]:
    if sys.platform.startswith('sunos'):
        # getifaddrs lives in libsocket on illumos/Solaris, not libc
        lib_name = ctypes.util.find_library('socket') or 'libsocket.so.1'
    elif sys.platform.startswith('haiku'):
        # getifaddrs lives in libnetwork on Haiku
        lib_name = ctypes.util.find_library('network') or 'libnetwork.so'
    else:
        lib_name = ctypes.util.find_library('c')
    libc = ctypes.CDLL(lib_name, use_errno=True)
    libc.getifaddrs.restype = ctypes.c_int
    libc.getifaddrs.argtypes = [ctypes.POINTER(ctypes.POINTER(_ifaddrs))]
    libc.freeifaddrs.argtypes = [ctypes.POINTER(_ifaddrs)]

    head = ctypes.POINTER(_ifaddrs)()
    if libc.getifaddrs(ctypes.byref(head)) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))

    result: Dict[str, List[InterfaceAddress]] = {}
    try:
        cur = head
        while cur:
            ifa = cur.contents
            cur = ifa.ifa_next  # advance now so 'continue' is safe

            if not ifa.ifa_name or not ifa.ifa_addr:
                continue

            flags = ifa.ifa_flags
            if not flags & _IFF_UP:
                continue
            if flags & _IFF_LOOPBACK:
                continue
            if not flags & _IFF_MULTICAST:
                continue

            fam = ifa.ifa_addr.contents.sa_family
            if fam == socket.AF_INET:
                sa = ctypes.cast(ifa.ifa_addr, ctypes.POINTER(_sockaddr_in)).contents
                addr = socket.inet_ntop(fam, bytes(sa.sin_addr))
            elif fam == socket.AF_INET6:
                sa = ctypes.cast(ifa.ifa_addr, ctypes.POINTER(_sockaddr_in6)).contents
                raw = bytes(sa.sin6_addr)
                if not _is_v6_link_local(raw):
                    continue
                addr = socket.inet_ntop(fam, _clean_v6_link_local(raw))
            else:
                continue

            name = ifa.ifa_name.decode()
            try:
                idx = socket.if_nametoindex(name)
            except OSError:
                continue

            result.setdefault(name, []).append((idx, fam, addr))
    finally:
        libc.freeifaddrs(head)
    return result


# --------------------------------------------------------------------------- #
# Windows: GetAdaptersAddresses
# --------------------------------------------------------------------------- #
# NOTE: struct layouts are reasoned against the documented IP_ADAPTER_*_LH
# definitions; not exercised on Windows in the development environment here.

if sys.platform == 'win32':
    from ctypes import wintypes

    _AF_UNSPEC = 0
    _ERROR_SUCCESS = 0
    _MAX_ADAPTER_ADDRESS_LENGTH = 8

    _IF_TYPE_SOFTWARE_LOOPBACK = 24
    _IF_OPER_STATUS_UP = 1
    _IP_ADAPTER_FLAG_NO_MULTICAST = 0x10  # bit 4 of the Flags bitfield

    class _SOCKET_ADDRESS(ctypes.Structure):
        _fields_ = [("lpSockaddr", ctypes.POINTER(_sockaddr)),
                    ("iSockaddrLength", ctypes.c_int)]

    class _IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
        pass

    _IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
        ("Length",             wintypes.ULONG),
        ("Flags",              wintypes.DWORD),
        ("Next",               ctypes.POINTER(_IP_ADAPTER_UNICAST_ADDRESS)),
        ("Address",            _SOCKET_ADDRESS),
        ("PrefixOrigin",       ctypes.c_int),
        ("SuffixOrigin",       ctypes.c_int),
        ("DadState",           ctypes.c_int),
        ("ValidLifetime",      wintypes.ULONG),
        ("PreferredLifetime",  wintypes.ULONG),
        ("LeaseLifetime",      wintypes.ULONG),
        ("OnLinkPrefixLength", ctypes.c_uint8),
    ]

    class _IP_ADAPTER_ADDRESSES(ctypes.Structure):
        pass

    _IP_ADAPTER_ADDRESSES._fields_ = [
        ("Length",                wintypes.ULONG),
        ("IfIndex",               wintypes.DWORD),
        ("Next",                  ctypes.POINTER(_IP_ADAPTER_ADDRESSES)),
        ("AdapterName",           ctypes.c_char_p),
        ("FirstUnicastAddress",   ctypes.POINTER(_IP_ADAPTER_UNICAST_ADDRESS)),
        ("FirstAnycastAddress",   ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix",             ctypes.c_wchar_p),
        ("Description",           ctypes.c_wchar_p),
        ("FriendlyName",          ctypes.c_wchar_p),
        ("PhysicalAddress",       ctypes.c_ubyte * _MAX_ADAPTER_ADDRESS_LENGTH),
        ("PhysicalAddressLength", wintypes.ULONG),
        ("Flags",                 wintypes.ULONG),
        ("Mtu",                   wintypes.ULONG),
        ("IfType",                wintypes.DWORD),
        ("OperStatus",            ctypes.c_uint),
        ("Ipv6IfIndex",           wintypes.DWORD),
    ]

    def _enum_windows() -> Dict[str, List[InterfaceAddress]]:
        fn = ctypes.windll.iphlpapi.GetAdaptersAddresses
        fn.restype = wintypes.ULONG
        fn.argtypes = [wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p,
                       ctypes.POINTER(_IP_ADAPTER_ADDRESSES),
                       ctypes.POINTER(wintypes.ULONG)]

        size = wintypes.ULONG(0)
        fn(_AF_UNSPEC, 0, None, None, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        head = ctypes.cast(buf, ctypes.POINTER(_IP_ADAPTER_ADDRESSES))
        ret = fn(_AF_UNSPEC, 0, None, head, ctypes.byref(size))
        if ret != _ERROR_SUCCESS:
            raise ctypes.WinError(ret)

        result: Dict[str, List[InterfaceAddress]] = {}
        cur = head
        while cur:
            adapter = cur.contents
            cur = adapter.Next

            if adapter.OperStatus != _IF_OPER_STATUS_UP:
                continue
            if adapter.IfType == _IF_TYPE_SOFTWARE_LOOPBACK:
                continue
            if adapter.Flags & _IP_ADAPTER_FLAG_NO_MULTICAST:
                continue

            name = adapter.FriendlyName
            if not name:
                continue

            ua = adapter.FirstUnicastAddress
            while ua:
                sa_ptr = ua.contents.Address.lpSockaddr
                ua = ua.contents.Next
                if not sa_ptr:
                    continue
                fam = sa_ptr.contents.sa_family
                if fam == socket.AF_INET:
                    sa = ctypes.cast(sa_ptr, ctypes.POINTER(_sockaddr_in)).contents
                    addr = socket.inet_ntop(fam, bytes(sa.sin_addr))
                    idx = adapter.IfIndex
                elif fam == socket.AF_INET6:
                    sa = ctypes.cast(sa_ptr, ctypes.POINTER(_sockaddr_in6)).contents
                    raw = bytes(sa.sin6_addr)
                    if not _is_v6_link_local(raw):
                        continue
                    addr = socket.inet_ntop(fam, _clean_v6_link_local(raw))
                    idx = adapter.Ipv6IfIndex
                else:
                    continue

                result.setdefault(name, []).append((idx, fam, addr))
        return result


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def enum_interfaces() -> Dict[str, List[InterfaceAddress]]:
    """Return ``{name: [(index, family, address), ...]}`` for usable interfaces.

    Loopback and non-multicast-capable interfaces are excluded, as are
    interfaces that aren't currently up. For IPv6, only link-local addresses
    (``fe80::/10``) are returned. The list for each interface preserves the
    order in which the OS reports addresses.
    """
    if sys.platform == 'win32':
        return _enum_windows()
    return _enum_unix()

def default_interface_address():
    """Return family and address of the default network interface. Prefers IPv4"""
    for family, dest in ((socket.AF_INET, ('8.8.8.8', 80)), (socket.AF_INET6, ('2001:4860:4860::8888', 80))):
        with socket.socket(family, socket.SOCK_DGRAM) as s:
            try:
                s.connect(dest)
                return family, s.getsockname()[0]
            except OSError:
                continue
    
    return None

