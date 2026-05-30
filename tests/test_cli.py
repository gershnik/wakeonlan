
# pylint: disable=missing-function-docstring,missing-module-docstring,use-implicit-booleaness-not-comparison

"""End-to-end CLI tests driven via subprocess.

Tests in this file would have caught the two recent regressions on the ipv6
branch (the `args.iface` typo and the tuple-vs-list isinstance mismatch), both
of which lived in the path from argparse to dispatch and were invisible to
tests that call the public Python functions directly.
"""

import json
import os
from pathlib import Path

import pytest

from wakeonlan import HostRecord, get_name_record, get_names


# --------------------------------------------------------------------------- #
# Save / wake-by-name roundtrip across all three host-record shapes
# --------------------------------------------------------------------------- #

def test_save_with_interface(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', '-i', 'eth0',
            expect_success=True)
    assert get_name_record('box') == HostRecord((1, 2, 3, 4, 5, 6), 'eth0', None, 9)


def test_save_with_deprecated_a_flag_warns_but_succeeds(run_cli):
    result = run_cli('--save', 'box', '01:02:03:04:05:06', '-a', '192.168.99.255',
                     expect_success=True)
    assert 'deprecated' in result.stderr.lower()
    assert get_name_record('box') == HostRecord(
        (1, 2, 3, 4, 5, 6), None, '192.168.99.255', 9)


def test_save_bare(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', expect_success=True)
    assert get_name_record('box') == HostRecord((1, 2, 3, 4, 5, 6), None, None, 9)


def test_save_with_port(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', '-p', '7', expect_success=True)
    assert get_name_record('box') == HostRecord((1, 2, 3, 4, 5, 6), None, None, 7)


def test_delete_removes_saved_record(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', expect_success=True)
    run_cli('--delete', 'box', expect_success=True)
    assert get_names() == {}


# --------------------------------------------------------------------------- #
# Direct wake routing -- catches the isinstance(list) vs tuple regression.
# A bare MAC on the CLI must reach WAKE_CMD, not get mis-routed to
# WAKE_BY_NAME and report "Name (1, 2, 3, ...) not found".
# --------------------------------------------------------------------------- #

def test_bare_mac_routes_to_wake_cmd(run_cli):
    result = run_cli('01:02:03:04:05:06', expect_success=True)
    assert 'wake:' in result.stdout
    assert 'not found' not in result.stdout


def test_wake_with_interface_prints_formatted_mac(run_cli):
    # Catches the "raw int list" formatting bug: WAKE_CMD
    # output must show the MAC as 01:02:03:04:05:06, not [1, 2, 3, ...].
    # Pick an interface dynamically since hardcoded names vary per platform/runner.
    from wakeonlan.interfaces import enum_interfaces
    ifaces = list(enum_interfaces())
    if not ifaces:
        pytest.skip('no eligible interfaces on this host')
    result = run_cli('01:02:03:04:05:06', '-i', ifaces[0], expect_success=True)
    assert '01:02:03:04:05:06' in result.stdout
    assert '[1, 2, 3, 4, 5, 6]' not in result.stdout


def test_wake_with_a_prints_formatted_mac_and_warns(run_cli):
    result = run_cli('01:02:03:04:05:06', '-a', '127.255.255.255',
                     expect_success=True)
    assert '01:02:03:04:05:06' in result.stdout
    assert 'deprecated' in result.stderr.lower()


def test_wake_by_name_resolves(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', '-a', '127.255.255.255',
            expect_success=True)
    result = run_cli('box', expect_success=True)
    assert '01:02:03:04:05:06' in result.stdout


def test_wake_by_nonexistent_name_errors(run_cli):
    result = run_cli('nonesuch', expect_success=False)
    assert 'not found' in (result.stdout + result.stderr).lower()


# --------------------------------------------------------------------------- #
# Anchoring + validation regression tests 
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize('bad_mac', [
    '01:02:03:04:05:06:99',   # seven groups
    '01:02:03:04:05:06X',     # trailing garbage
    'gg:gg:gg:gg:gg:gg',      # non-hex
    '01:02:03:04:05',         # five groups
])
def test_invalid_mac_is_not_treated_as_mac(run_cli, bad_mac):
    # These strings shouldn't validate as MACs (they fall to name lookup),
    # so the CLI must error rather than build a magic packet.
    result = run_cli(bad_mac, expect_success=False)
    assert 'wake:' not in result.stdout


@pytest.mark.parametrize('bad_ip', [
    '192.168.1.1garbage',     # trailing garbage
    '192.168.1.1.1',          # five octets
    '999.1.1.1',              # out of range
])
def test_invalid_ip_rejected_on_a_flag(run_cli, bad_ip):
    result = run_cli('01:02:03:04:05:06', '-a', bad_ip, expect_success=False)
    assert 'invalid' in (result.stdout + result.stderr).lower()


def test_port_65535_accepted(run_cli):
    result = run_cli('01:02:03:04:05:06', '-p', '65535', expect_success=True)
    assert ', 65535' in result.stdout


def test_port_negative_rejected(run_cli):
    run_cli('01:02:03:04:05:06', '-p', '-1', expect_success=False)


def test_port_65536_rejected(run_cli):
    run_cli('01:02:03:04:05:06', '-p', '65536', expect_success=False)


def test_port_non_integer_rejected(run_cli):
    run_cli('01:02:03:04:05:06', '-p', 'abc', expect_success=False)


# --------------------------------------------------------------------------- #
# Mutual exclusion -- catches dispatch-table refactors that drop checks
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize('argv,expected', [
    (['--list', '-i', 'eth0'],                  'not allowed with --list'),
    (['--list', '-p', '9'],                     'not allowed with'),
    (['--delete', 'x', '-i', 'eth0'],           'not allowed with --delete'),
    (['--names', '-i', 'eth0'],                 'not allowed with --names'),
    (['saved_name', '-i', 'eth0'],              'Cannot specify interface with name'),
    (['saved_name', '-p', '9'],                 'Cannot specify port with name'),
    (['01:02:03:04:05:06', '-i', 'eth0', '-a', '1.2.3.4'],
                                                'Cannot specify both'),
])
def test_invalid_combinations_rejected(run_cli, argv, expected):
    result = run_cli(*argv, expect_success=False)
    assert expected in (result.stdout + result.stderr)


def test_save_without_mac_rejected(run_cli):
    result = run_cli('--save', 'box', expect_success=False)
    assert 'MAC' in (result.stdout + result.stderr)


# --------------------------------------------------------------------------- #
# Listing commands -- output shape
# --------------------------------------------------------------------------- #

def test_list_shows_all_three_record_shapes(run_cli):
    run_cli('--save', 'by_iface', '01:02:03:04:05:06', '-i', 'eth0',
            expect_success=True)
    run_cli('--save', 'by_ip', '0A:0B:0C:0D:0E:0F', '-a', '192.168.99.255',
            expect_success=True)
    run_cli('--save', 'bare', '11:22:33:44:55:66', expect_success=True)

    result = run_cli('--list', expect_success=True)
    out = result.stdout
    assert 'by_iface - 01:02:03:04:05:06, eth0, 9' in out
    assert 'by_ip - 0A:0B:0C:0D:0E:0F, 192.168.99.255, 9' in out
    assert 'bare - 11:22:33:44:55:66, *, 9' in out


def test_names_lists_just_the_names(run_cli):
    run_cli('--save', 'alpha', '01:02:03:04:05:06', expect_success=True)
    run_cli('--save', 'beta', '0A:0B:0C:0D:0E:0F', expect_success=True)

    result = run_cli('--names', expect_success=True)
    names = result.stdout.split()
    assert 'alpha' in names
    assert 'beta' in names
    assert len(names) == 2


def test_interfaces_returns_at_least_something(run_cli):
    # We don't know what interfaces a CI runner has, but on any host that can
    # do networking enum_interfaces should produce at least one line, and the
    # command must succeed without error.
    result = run_cli('--interfaces', expect_success=True)
    # Don't assert on contents -- the runner's interface list is what it is --
    # but the command must succeed.
    assert result.returncode == 0


# --------------------------------------------------------------------------- #
# Informational flags
# --------------------------------------------------------------------------- #

def test_version(run_cli):
    result = run_cli('--version', expect_success=True)
    assert 'wakeonlan' in result.stdout.lower()


def test_help(run_cli):
    result = run_cli('--help', expect_success=True)
    out = result.stdout.lower()
    assert 'usage' in out
    assert '-i' in result.stdout
    assert '--save' in result.stdout


# --------------------------------------------------------------------------- #
# Schema on disk -- the JSON shape is part of the user contract
# --------------------------------------------------------------------------- #

def test_save_writes_interface_key_when_using_i(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', '-i', 'eth0',
            expect_success=True)
    config = json.loads(Path(os.environ['WAKEONLAN_HOME'], '.wakeonlan').read_text(encoding='utf-8'))
    assert config['names']['box'] == {'mac': '01:02:03:04:05:06', 'interface': 'eth0'}


def test_save_writes_ip_key_when_using_a(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', '-a', '192.168.99.255',
            expect_success=True)
    config = json.loads(Path(os.environ['WAKEONLAN_HOME'], '.wakeonlan').read_text(encoding='utf-8'))
    record = config['names']['box']
    assert record['mac'] == '01:02:03:04:05:06'
    assert record['ip'] == '192.168.99.255'
    assert 'interface' not in record


def test_save_bare_writes_only_mac(run_cli):
    run_cli('--save', 'box', '01:02:03:04:05:06', expect_success=True)
    config = json.loads(Path(os.environ['WAKEONLAN_HOME'], '.wakeonlan').read_text(encoding='utf-8'))
    assert config['names']['box'] == {'mac': '01:02:03:04:05:06'}
