
# pylint: disable=missing-function-docstring,missing-module-docstring

"""Tests for the magic packet itself.

The cost of getting the packet bytes wrong is silent failure to wake, so
these are belt-and-suspenders even though the helper is tiny.
"""

import socket

import pytest

from wakeonlan.wakeonlan import _payload, _wake_with_dest


def test_payload_is_exactly_102_bytes():
    payload = _payload((0x01, 0x02, 0x03, 0x04, 0x05, 0x06))
    assert len(payload) == 102


def test_payload_starts_with_six_0xff():
    payload = _payload((0x01, 0x02, 0x03, 0x04, 0x05, 0x06))
    assert bytes(payload[:6]) == b'\xff' * 6


def test_payload_then_repeats_mac_sixteen_times():
    mac = (0x01, 0x02, 0x03, 0x04, 0x05, 0x06)
    payload = _payload(mac)
    expected_tail = bytes(mac) * 16
    assert bytes(payload[6:]) == expected_tail
    assert len(payload) == 6 + len(expected_tail)


@pytest.mark.parametrize('mac', [
    (0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    (0xff, 0xff, 0xff, 0xff, 0xff, 0xff),
    (0xde, 0xad, 0xbe, 0xef, 0xca, 0xfe),
])
def test_payload_byte_for_byte(mac):
    expected = b'\xff' * 6 + bytes(mac) * 16
    assert bytes(_payload(mac)) == expected


# --------------------------------------------------------------------------- #
# End-to-end: actually emit a packet and recv it on a local UDP socket.
# This catches a class of bug a pure in-memory test would miss -- e.g. the
# getaddrinfo path picking the wrong family, or SO_BROADCAST being needed for
# loopback under some kernels.
# --------------------------------------------------------------------------- #

def test_wake_with_dest_actually_transmits_correct_packet():
    mac = (0x01, 0x02, 0x03, 0x04, 0x05, 0x06)
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        rx.bind(('127.0.0.1', 0))
        rx.settimeout(2)
        port = rx.getsockname()[1]
        _wake_with_dest(mac, ('127.0.0.1', port))
        data, _ = rx.recvfrom(200)
    finally:
        rx.close()
    assert data == b'\xff' * 6 + bytes(mac) * 16
