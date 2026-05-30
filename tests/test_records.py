
# pylint: disable=missing-function-docstring,missing-module-docstring,use-implicit-booleaness-not-comparison,unused-argument

"""Tests for HostRecord behavior and config-file parsing.

These tests drive the Python API directly (no subprocess) because they
exercise parsing/validation logic that doesn't depend on the CLI path.
"""

import pytest

from wakeonlan import HostRecord, WakeOnLanError, get_name_record, get_names


# --------------------------------------------------------------------------- #
# HostRecord display helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize('iface,addr,expected', [
    ('eth0', None,            'eth0'),
    (None,   '192.168.1.255', '192.168.1.255'),
    (None,   None,            '*'),
    # interface wins when both are populated (an unusual but defensible case)
    ('eth0', '192.168.1.255', 'eth0'),
])
def test_interface_name_display(iface, addr, expected):
    rec = HostRecord((1, 1, 1, 1, 1, 1), iface, addr, 9)
    assert rec.interface_name() == expected


def test_mac_str_uppercase_hex():
    assert HostRecord(
        (0xab, 0xcd, 0x01, 0x02, 0x03, 0x04), None, None, 9
    ).mac_str() == 'AB:CD:01:02:03:04'


def test_mac_str_zero_padded():
    assert HostRecord(
        (0, 1, 2, 0xf, 0x10, 0xff), None, None, 9
    ).mac_str() == '00:01:02:0F:10:FF'


# --------------------------------------------------------------------------- #
# Backward compatibility for old-style configs
# --------------------------------------------------------------------------- #

def test_legacy_record_with_only_mac_loads(write_config):
    write_config({'names': {'box': {'mac': '01:02:03:04:05:06'}}})
    assert get_name_record('box') == HostRecord(
        (1, 2, 3, 4, 5, 6), None, None, 9)


def test_legacy_record_with_ip_loads(write_config):
    write_config({'names': {'box': {
        'mac': '01:02:03:04:05:06', 'ip': '192.168.99.255'}}})
    assert get_name_record('box') == HostRecord(
        (1, 2, 3, 4, 5, 6), None, '192.168.99.255', 9)


def test_record_with_interface_loads(write_config):
    write_config({'names': {'box': {
        'mac': '01:02:03:04:05:06', 'interface': 'eth0'}}})
    assert get_name_record('box') == HostRecord(
        (1, 2, 3, 4, 5, 6), 'eth0', None, 9)


def test_record_with_default_ip_normalizes_to_none(write_config):
    # A saved "ip": "255.255.255.255" -- the default -- should round-trip back
    # as the None broadcast sentinel rather than a literal address.
    write_config({'names': {'box': {
        'mac': '01:02:03:04:05:06', 'ip': '255.255.255.255'}}})
    rec = get_name_record('box')
    assert rec is not None
    assert rec.address is None


def test_record_with_interface_and_ip_prefers_interface(write_config):
    # If both keys are present (shouldn't happen from save, but the file
    # could be hand-edited), parsing should resolve to interface-only.
    write_config({'names': {'box': {
        'mac': '01:02:03:04:05:06',
        'interface': 'eth0',
        'ip': '192.168.99.255'}}})
    rec = get_name_record('box')
    assert rec is not None
    assert rec.interface == 'eth0'
    assert rec.address is None


def test_record_with_explicit_port(write_config):
    write_config({'names': {'box': {
        'mac': '01:02:03:04:05:06', 'port': 7}}})
    rec = get_name_record('box')
    assert rec is not None
    assert rec.port == 7


# --------------------------------------------------------------------------- #
# Malformed configs raise WakeOnLanError
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize('record,reason', [
    ({},                                            'mac missing'),
    ({'mac': 'not-a-mac'},                          'mac malformed'),
    ({'mac': '01:02:03:04:05:06:07'},               'mac has extra group'),
    ({'mac': '01:02:03:04:05:06garbage'},           'mac trailing garbage'),
    ({'mac': '01:02:03:04:05:06', 'port': -1},      'port negative'),
    ({'mac': '01:02:03:04:05:06', 'port': 70000},   'port too large'),
    ({'mac': '01:02:03:04:05:06', 'port': 'nine'},  'port not integer'),
    ({'mac': '01:02:03:04:05:06', 'ip': 'x.y.z'},   'ip malformed'),
    ({'mac': '01:02:03:04:05:06', 'ip': '192.168.1.1.5'}, 'ip too many octets'),
    ([1, 2, 3],                                     'record not a dict'),
])
def test_malformed_record_rejected(write_config, record, reason):
    write_config({'names': {'test': record}})
    with pytest.raises(WakeOnLanError):
        get_name_record('test')


def test_top_level_not_a_dict(write_config):
    write_config([1, 2, 3])
    with pytest.raises(WakeOnLanError):
        get_name_record('anything')


def test_missing_names_key(write_config):
    write_config({'something_else': {}})
    with pytest.raises(WakeOnLanError):
        get_name_record('anything')


def test_truncated_json_file():
    # Bypass write_config because we need invalid JSON
    import os
    from pathlib import Path
    path = Path(os.environ['WAKEONLAN_HOME']) / '.wakeonlan'
    path.write_text('{"names": {"x": {"mac": "01:02:0', encoding='utf-8')
    with pytest.raises(WakeOnLanError):
        get_name_record('x')


# --------------------------------------------------------------------------- #
# Get-all-names returns every record
# --------------------------------------------------------------------------- #

def test_get_names_with_multiple_records(write_config):
    write_config({'names': {
        'a': {'mac': '01:02:03:04:05:06', 'interface': 'eth0'},
        'b': {'mac': '0A:0B:0C:0D:0E:0F', 'ip': '192.168.99.255'},
        'c': {'mac': '11:22:33:44:55:66'},
    }})
    names = get_names()
    assert set(names.keys()) == {'a', 'b', 'c'}
    assert names['a'].interface == 'eth0'
    assert names['b'].address == '192.168.99.255'
    assert names['c'].interface is None and names['c'].address is None


def test_get_names_empty():
    assert get_names() == {}


def test_get_name_record_nonexistent():
    assert get_name_record('nonesuch') is None
