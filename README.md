# wakeonlan #

[![License][badge-license]][license]
[![pypi][badge-pypi]][wakeonlan-pypi]
[![Language][badge-lang]][python]

An advanced wake-on-lan command line script and library.

<!-- TOC depthfrom:2 -->

- [Why another one?](#why-another-one)
- [Setup](#setup)
- [Usage](#usage)
    - [Wake up a machine given its MAC address XX:XX:XX:XX:XX:XX](#wake-up-a-machine-given-its-mac-address-xxxxxxxxxxxx)
    - [Save wake up configuration to be used later](#save-wake-up-configuration-to-be-used-later)
    - [Wake up a machine given saved configuration name](#wake-up-a-machine-given-saved-configuration-name)
    - [List existing configuration names](#list-existing-configuration-names)
    - [Delete a configuration](#delete-a-configuration)
    - [List available interfaces](#list-available-interfaces)
    - [Transferring configurations to another machine](#transferring-configurations-to-another-machine)
- [Set up shell autocomplete](#set-up-shell-autocomplete)
    - [Bash](#bash)
    - [Zsh](#zsh)
    - [Powershell](#powershell)
- [Backward compatibility](#backward-compatibility)
- [Programmatic access](#programmatic-access)

<!-- /TOC -->


## Why another one?

I couldn't find one that worked and did what I need. Specifically I need:
* A command line utility that works on Mac, Windows and Linux.
* Works over both IPv4 and IPv6, including on IPv6-only networks.
* Can use saved configurations rather than force me to remember the MAC addresses of the machines I need to wake.
* Ideally, let me manipulate (create, delete, update, list) saved configurations using the same utility.
* Ideally, be open source so I can see what it is doing and know it doesn't do anything nefarious

None of the existing tools I found satisfied these criteria (even without the last two) so I wrote my own.

## Setup

**Prerequisites**: Python 3.7 or above. No additional packages required.

```bash
pip3 install eg.wakeonlan
```

> **Tip:**
> On Windows, if you get a warning like:
> ```
> WARNING: The script wakeonlan.exe is installed in 
> 'C:\Users\[username]\AppData\Roaming\Python\Python[VER]\Scripts' which is not on PATH.
> ```
>
> You can either add this directory to your PATH or run `pip3 install` from Administrator command prompt.
>
> The reason for this message is that Python does not add _per user_ scripts directory to PATH on Windows, 
> only the system-wide one. See [this Python bug](https://bugs.python.org/issue39658)

On macOS, if you use Homebrew, you can also get the command-line tool independent of a specific Python version via:

```bash
brew tap gershnik/repo
brew install eg-wakeonlan
```
> **Note:**
> Homebrew installs only the command-line tool. If you want to use the library programmatically (import wakeonlan), 
> use the `pip` approach above.

## Usage


### Wake up a machine given its MAC address XX:XX:XX:XX:XX:XX 

```bash
wakeonlan XX:XX:XX:XX:XX:XX [-i InterfaceName] [-p Port]
```

The `-i` option allows you to specify the interface to send wake-on-lan packet from.
If not specified, it will be sent from _all_ eligible interfaces (those that are active, not loopback and allow broadcasts/multicasts).

You can see all the eligible interface names by invoking `wakeonlan --interfaces`.

Both IPv4 and IPv6 interfaces are supported. Because wake-on-lan might be more reliable over IPv4 (depending on destination machine software),
`wakeonlan` prefers IPv4 when both are available on the same interface.

The `-p` option allows you to override the destination port (9 if omitted).

### Save wake up configuration to be used later

```bash
wakeonlan --save Name XX:XX:XX:XX:XX:XX [-i InterfaceName] [-p Port]
```

Name can be anything. The configuration is saved into `$HOME/.wakeonlan` file in JSON format.

`--save` can be abbreviated as `-s`.

### Wake up a machine given saved configuration name

```bash
wakeonlan Name
```

### List existing configuration names

```bash
wakeonlan --names
```

`--names` can be abbreviated as `-n`.

If you want to see full details about each name, use:

```bash
wakeonlan --list
```

`--list` can be abbreviated as `-l`.

### Delete a configuration

```bash
wakeonlan --delete Name
```

`--delete` can be abbreviated as `-d`.

### List available interfaces

```bash
wakeonlan --interfaces
```

This will print out a list of interface names usable with the `-i` flag.

### Transferring configurations to another machine

Saved configurations are stored in `$HOME/.wakeonlan` file (`%USERPROFILE%\.wakeonlan` for Windows users).
Copy this file to another machine into the equivalent location to transfer all the configurations.

## Set up shell autocomplete

Autocomplete is supported for `bash`, `zsh` and `powershell`.

### Bash

Add the following to your `~/.bashrc`:

```bash
source `wakeonlan --autocomplete-source`
```

### Zsh

Add the following to your `~/.zshrc` (make sure it is *after* the call to `compinit`):

```bash
source `wakeonlan --autocomplete-source`
```

### Powershell

1. If you haven't already done so, you will need to enable script execution on your machine.
  ```ps
  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
2. Remove "mark of the web" from the auto-complete script:
  ```ps
  Unblock-File -Path $(wakeonlan --autocomplete-source)
  ```
3. Find the location of your profile file:
  ```ps
  echo $profile
  ```
4. If it doesn't exist, create it. Then add the following to its content:
  ```ps
  . $(wakeonlan --autocomplete-source)
  ```

## Backward compatibility

`wakeonlan` fully supports configurations created by older versions and the now-deprecated `-a` switch.
If you have a configuration with a non-default `-a` setting, it continues to function as before. A default `-a`
(255.255.255.255) in the saved configuration behaves as if no switches were specified - the wake-on-lan packet 
is sent on _all_ eligible interfaces, including IPv6 ones. 
(On older versions it would be sent only on the default IPv4 interface). 

Using the `-a` switch on the command line now produces a deprecation warning but continues to function exactly as before.
Specifically, using `-a 255.255.255.255` on the command line continues to send a single IPv4 broadcast to that address.

## Programmatic access

```python

import wakeonlan

# wake a given MAC using all the defaults
wakeonlan.wake(wakeonlan.HostRecord((1,2,3,4,5,6)))
# or specify some options
wakeonlan.wake(wakeonlan.HostRecord((1,2,3,4,5,6), interface='eth0', port=9))
# save a record in user's configuration
wakeonlan.save_name("my-machine", wakeonlan.HostRecord((1,2,3,4,5,6)))
# get it back
rec = wakeonlan.get_name_record("my-machine")
# get all records
for name, rec in wakeonlan.get_names().items():
    print(name, rec.mac_str())
# delete a record
wakeonlan.delete_name("my-machine")
```

See the sources for more details.

<!-- Links -->

[badge-license]: https://img.shields.io/badge/license-BSD-brightgreen.svg
[license]: https://opensource.org/licenses/BSD-3-Clause
[badge-pypi]: https://img.shields.io/pypi/v/eg.wakeonlan
[wakeonlan-pypi]: https://pypi.org/project/eg.wakeonlan
[badge-lang]: https://img.shields.io/badge/language-Python-blue.svg
[python]: https://www.python.org

<!-- End Links -->
