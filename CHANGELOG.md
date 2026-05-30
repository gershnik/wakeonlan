# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),

## Unreleased

Major release. Existing saved configurations and the `wakeonlan NAME` / `wakeonlan MAC` command lines continue to work without changes; some Python API consumers will need to update (see **Changed** below).

### Added
- `-i INTERFACE_NAME` flag to send the wake packet from a specific network interface. This replaces `-a` as the recommended way to target a particular network on machines with multiple interfaces. Run `wakeonlan --interfaces` to see the available interface names.
- `--interfaces` command listing the network interfaces wakeonlan can use.
- Wake-on-LAN now works over IPv6. On machines with both IPv4 and IPv6, the appropriate protocol is used for each interface automatically.
- Saved entries can now record an interface name instead of (or in addition to) a broadcast address. Use `wakeonlan --save NAME MAC -i INTERFACE_NAME`.
- Shell autocomplete (bash/zsh/PowerShell) now completes interface names after `-i`.
- Error and warning messages are colored when run in a terminal on Python 3.14+, matching the style of Python's own command-line tools.
- The package now exports `HostRecord`, `MacAddress`, `IPAddress`, `Port`, and `WakeOnLanError`, plus an `enum_interfaces` function in `wakeonlan.interfaces`, for programmatic use.

### Changed
- When neither `-i` nor `-a` is given, the wake packet is now sent on **every** eligible network interface, not just the system's default. This makes wake-up reliably reach machines on the secondary network of a multi-homed host (Wi-Fi + Ethernet, VPN, container networks, etc.).
- Configuration entries now use an `"interface"` key alongside the legacy `"ip"` key. Old configuration files continue to load unchanged; saving a new entry with `-i` writes the new format.
- **Python API:** `HostRecord` is now a `NamedTuple` with `mac`, `interface`, `address`, and `port` fields and `mac_str()` / `interface_name()` helpers, replacing the previous nested-tuple shape.
- **Python API:** `wake(record)` takes a single `HostRecord` instead of `wake(mac, addr)`.
- **Python API:** `save_name(name, record)` takes a `HostRecord` instead of `save_name(name, mac, ipaddr, port)`.

### Deprecated
- `-a IP_ADDRESS` is deprecated in favor of `-i INTERFACE_NAME`. The flag still works and prints a one-line deprecation notice; it may be removed in a future release.

### Fixed
- Port `65535` is now accepted on the command line (previously rejected, despite being accepted in configuration files).
- MAC and IP arguments with trailing garbage (e.g. `01:02:03:04:05:06:99` or `192.168.1.1xxx`) are now rejected; previously the parser would silently accept the leading prefix.
- The MAC address in the `wake:` status message is shown in canonical `XX:XX:XX:XX:XX:XX` form. Previously it could appear as `[1, 2, 3, 4, 5, 6]`.
- Saving the configuration file is now atomic — an interrupted save no longer corrupts the file or leaves stray temp files behind.

## [1.3] - 2024-08-17

### Changed
- Module's public interface is now finalized
- Code cleaned to conform to various PEPs and make PyLint happy

## [1.2] - 2024-05-09

### Added
- Support for shell autocomplete for `bash`, `zsh` and `powershell`. 

## [1.1] - 2024-04-27

### Changed
- The script is now a proper Python package and is distributed via PyPi


## [1.0] - 2020-10-21
### Added
- Initial release


[1.0]: https://github.com/gershnik/wakeonlan/releases/1.0
[1.1]: https://github.com/gershnik/wakeonlan/releases/1.1
[1.2]: https://github.com/gershnik/wakeonlan/releases/1.2
[1.3]: https://github.com/gershnik/wakeonlan/releases/1.3
