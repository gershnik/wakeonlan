
# pylint: disable=missing-function-docstring,missing-module-docstring

"""Cross-check enum_interfaces() against what platform-native CLI tools report.

Each test discovers the appropriate tool for the running platform and skips
gracefully if either the platform isn't a match or the tool isn't available.
The CLI is treated as ground truth: enum_interfaces' set of (name, address)
tuples must be a subset of what the CLI reports for up + non-loopback +
multicast-capable interfaces. The reverse direction is asserted as well,
modulo the small race window of an interface coming up or going down between
the two calls -- which is why a single mismatching interface is tolerated.
"""

import ipaddress
import json
import re
import shutil
import socket
import subprocess
import sys
from typing import Dict, Set, Tuple

import pytest

from wakeonlan.interfaces import enum_interfaces

# Per-interface (ipv4 addresses, ipv6 link-local addresses)
InterfaceAddrs = Tuple[Set[str], Set[str]]


# --------------------------------------------------------------------------- #
# Build the comparable view of what enum_interfaces returned
# --------------------------------------------------------------------------- #

def _enum_view() -> Dict[str, InterfaceAddrs]:
    out: Dict[str, InterfaceAddrs] = {}
    for name, addrs in enum_interfaces().items():
        v4: Set[str] = set()
        v6: Set[str] = set()
        for _idx, fam, addr in addrs:
            bare = addr.split('%', 1)[0]
            if fam == socket.AF_INET:
                v4.add(bare)
            elif fam == socket.AF_INET6:
                v6.add(bare)
        out[name] = (v4, v6)
    return out


def _compare(cli: Dict[str, InterfaceAddrs],
             enum: Dict[str, InterfaceAddrs]) -> None:
    # enum should not invent interfaces the CLI doesn't see
    extra = set(enum) - set(cli)
    assert not extra, (
        f'enum_interfaces reports interfaces the CLI does not: {extra}\n'
        f'cli set:  {sorted(cli)}\nenum set: {sorted(enum)}')

    # symmetric direction, tolerating up to one race-window difference
    missing = set(cli) - set(enum)
    assert len(missing) <= 1, (
        f'enum_interfaces is missing interfaces the CLI reports: {missing}\n'
        f'cli set:  {sorted(cli)}\nenum set: {sorted(enum)}')

    for name, (e_v4, e_v6) in enum.items():
        c_v4, c_v6 = cli[name]
        assert e_v4 <= c_v4, (
            f'{name}: enum has IPv4 addresses the CLI does not: {e_v4 - c_v4}')
        assert e_v6 <= c_v6, (
            f'{name}: enum has IPv6 addresses the CLI does not: {e_v6 - c_v6}')


# --------------------------------------------------------------------------- #
# Linux: ip(8) from iproute2, JSON output
# --------------------------------------------------------------------------- #

def _linux_cli_view() -> Dict[str, InterfaceAddrs]:
    raw = subprocess.check_output(['ip', '-j', 'addr', 'show'], text=True)
    data = json.loads(raw)
    out: Dict[str, InterfaceAddrs] = {}
    for iface in data:
        flags = set(iface.get('flags', []))
        if 'LOOPBACK' in flags:
            continue
        if 'UP' not in flags:
            continue
        if 'MULTICAST' not in flags:
            continue
        v4: Set[str] = set()
        v6: Set[str] = set()
        for a in iface.get('addr_info', []):
            local = a.get('local', '')
            if a.get('family') == 'inet':
                v4.add(local)
            elif a.get('family') == 'inet6':
                try:
                    if ipaddress.IPv6Address(local).is_link_local:
                        v6.add(local)
                except ValueError:
                    continue
        out[iface['ifname']] = (v4, v6)
    return {name: addrs for name, addrs in out.items() if addrs[0] or addrs[1]}


@pytest.mark.skipif(
    sys.platform != 'linux' or not shutil.which('ip'),
    reason='requires Linux with the iproute2 `ip` command')
def test_enum_matches_linux_ip():
    _compare(_linux_cli_view(), _enum_view())


# --------------------------------------------------------------------------- #
# macOS / *BSD: ifconfig(8)
# --------------------------------------------------------------------------- #

def _bsd_cli_view() -> Dict[str, InterfaceAddrs]:
    raw = subprocess.check_output(['ifconfig', '-a'], text=True)
    out: Dict[str, InterfaceAddrs] = {}
    current = None
    keep = False
    v4: Set[str] = set()
    v6: Set[str] = set()

    def commit():
        if keep and current is not None and (v4 or v6):
            out[current] = (v4.copy(), v6.copy())

    header = re.compile(r'^(\S+):\s+flags=\d+<([^>]*)>')
    for line in raw.splitlines():
        if line and not line[0].isspace():
            commit()
            v4, v6 = set(), set()
            m = header.match(line)
            if not m:
                current, keep = None, False
                continue
            current = m.group(1)
            flags = set(m.group(2).split(','))
            keep = ('LOOPBACK' not in flags
                    and 'UP' in flags
                    and 'MULTICAST' in flags)
            continue
        if not keep:
            continue
        stripped = line.strip()
        m4 = re.match(r'inet (\d+\.\d+\.\d+\.\d+)', stripped)
        if m4:
            v4.add(m4.group(1))
            continue
        m6 = re.match(r'inet6 (\S+)', stripped)
        if m6:
            addr = m6.group(1).split('%', 1)[0]
            try:
                if ipaddress.IPv6Address(addr).is_link_local:
                    v6.add(addr)
            except ValueError:
                pass
    commit()
    return out


@pytest.mark.skipif(
    not (sys.platform == 'darwin' or 'bsd' in sys.platform)
    or not shutil.which('ifconfig'),
    reason='requires macOS or BSD with ifconfig')
def test_enum_matches_macos_or_bsd_ifconfig():
    _compare(_bsd_cli_view(), _enum_view())


# --------------------------------------------------------------------------- #
# Windows: PowerShell Get-NetAdapter + Get-NetIPAddress
# --------------------------------------------------------------------------- #

_WIN_PS_SCRIPT = r'''
$adapters = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.ifType -ne 24 }
$result = @{}
foreach ($a in $adapters) {
    $addrs = Get-NetIPAddress -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue
    $v4 = @()
    $v6 = @()
    foreach ($addr in $addrs) {
        $bare = ($addr.IPAddress -split '%')[0]
        if ($addr.AddressFamily -eq 'IPv4') { $v4 += $bare }
        elseif ($addr.AddressFamily -eq 'IPv6') { $v6 += $bare }
    }
    $result[$a.Name] = @{ v4 = $v4; v6 = $v6 }
}
$result | ConvertTo-Json -Depth 4 -Compress
'''


def _windows_powershell_bin():
    return shutil.which('pwsh') or shutil.which('powershell')


def _windows_cli_view() -> Dict[str, InterfaceAddrs]:
    ps = _windows_powershell_bin()
    assert ps is not None
    raw = subprocess.check_output(
        [ps, '-NoProfile', '-Command', _WIN_PS_SCRIPT], text=True)
    data = json.loads(raw) if raw.strip() else {}
    out: Dict[str, InterfaceAddrs] = {}
    for name, addrs in data.items():
        v4 = set(addrs.get('v4') or [])
        v6_raw = set(addrs.get('v6') or [])
        v6 = {a for a in v6_raw if _is_link_local(a)}
        if v4 or v6:
            out[name] = (v4, v6)
    return out


def _is_link_local(addr: str) -> bool:
    try:
        return ipaddress.IPv6Address(addr).is_link_local
    except ValueError:
        return False


@pytest.mark.skipif(
    sys.platform != 'win32' or _windows_powershell_bin() is None,
    reason='requires Windows with PowerShell (powershell.exe or pwsh)')
def test_enum_matches_windows_powershell():
    _compare(_windows_cli_view(), _enum_view())
