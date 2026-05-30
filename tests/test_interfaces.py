
# pylint: disable=missing-function-docstring,missing-module-docstring

"""Tests for the interfaces module's pure helpers and `enum_interfaces` sanity.

The OS-specific paths in `enum_interfaces` are hard to fully unit-test without
faking the kernel, so we lean on (a) pure helpers that are platform-independent
and (b) a couple of weak sanity checks against the actual host the test runs on.
"""

import ipaddress
import socket
import sys

import pytest

from wakeonlan.interfaces import (
    _clean_v6_link_local,
    _is_v6_link_local,
    enum_interfaces,
)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize('addr,expected', [
    ('fe80::1',         True),
    ('fe80::abcd:1234', True),
    ('febf::1',         True),    # top of the fe80::/10 range
    ('fec0::1',         False),   # deprecated site-local, not link-local
    ('2001:db8::1',     False),
    ('::1',             False),
    ('::',              False),
    ('ff02::1',         False),   # multicast, not unicast link-local
])
def test_is_v6_link_local(addr, expected):
    packed = ipaddress.IPv6Address(addr).packed
    assert _is_v6_link_local(packed) == expected


def test_clean_v6_link_local_strips_linux_scope_id():
    # Linux getifaddrs embeds the interface index in bytes 2-3 of the address
    # for link-local entries. Cleanup must zero them so inet_ntop produces the
    # canonical textual form.
    embedded = bytes.fromhex('fe800003' + '00' * 11 + '01')
    cleaned = _clean_v6_link_local(embedded)
    assert socket.inet_ntop(socket.AF_INET6, cleaned) == 'fe80::1'


def test_clean_v6_link_local_no_op_on_already_clean():
    clean = ipaddress.IPv6Address('fe80::1').packed
    assert _clean_v6_link_local(clean) == clean


def test_clean_v6_link_local_no_op_on_non_link_local():
    # Non-link-local addresses should pass through untouched, since bytes 2-3
    # carry real address bits there.
    other = ipaddress.IPv6Address('2001:db8:beef::1').packed
    assert _clean_v6_link_local(other) == other


# --------------------------------------------------------------------------- #
# Live sanity -- best-effort, doesn't assert too much about runner topology
# --------------------------------------------------------------------------- #

def test_enum_interfaces_returns_a_dict():
    result = enum_interfaces()
    assert isinstance(result, dict)


def test_enum_interfaces_excludes_loopback():
    # On every supported platform the loopback interface should be filtered.
    # The interface name varies (lo, lo0, Loopback Pseudo-Interface 1, ...)
    # but none of them should have a 127.0.0.1 entry surfaced through here.
    result = enum_interfaces()
    for name, addrs in result.items():
        for _idx, family, addr in addrs:
            if family == socket.AF_INET:
                assert not addr.startswith('127.'), (
                    f'loopback address {addr} on {name!r} should be filtered')


def test_enum_interfaces_ipv6_entries_are_link_local():
    # The module documents that only link-local v6 addresses are returned.
    result = enum_interfaces()
    for _name, addrs in result.items():
        for _idx, family, addr in addrs:
            if family == socket.AF_INET6:
                # Strip a possible zone suffix before testing (we don't append
                # one, but be tolerant if the implementation ever does)
                bare = addr.split('%', 1)[0]
                assert ipaddress.IPv6Address(bare).is_link_local, (
                    f'{addr} should be link-local')


def test_enum_interfaces_entries_have_valid_indices():
    result = enum_interfaces()
    for _name, addrs in result.items():
        for idx, _family, _addr in addrs:
            assert isinstance(idx, int)
            assert idx > 0     # 0 is reserved / "any"


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='if_nametoindex name format differs on Windows')
def test_enum_interfaces_indices_match_if_nametoindex():
    # On Unix, the index reported by enum_interfaces should match what
    # socket.if_nametoindex returns for the same name.
    for name, addrs in enum_interfaces().items():
        for idx, _family, _addr in addrs:
            assert idx == socket.if_nametoindex(name)
