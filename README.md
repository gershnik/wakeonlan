# wakeonlan #

[![License](https://img.shields.io/badge/license-BSD-brightgreen.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![pypi](https://img.shields.io/pypi/v/eg.wakeonlan)](https://pypi.org/project/eg.wakeonlan)
[![Language](https://img.shields.io/badge/language-Python-blue.svg)](https://isocpp.org/)
[![python](https://img.shields.io/badge/python->=3.7-blue.svg)](https://www.python.org)

Yet another wake-on-lan command line script.

<!-- TOC depthfrom:2 -->

- [Why another one?](#why-another-one)
- [Setup](#setup)
- [Usage](#usage)
    - [Wake up a machine given its MAC address XX:XX:XX:XX:XX:XX](#wake-up-a-machine-given-its-mac-address-xxxxxxxxxxxx)
    - [Save wake up configuration to be used later](#save-wake-up-configuration-to-be-used-later)
    - [Wake up a machine given saved configuration name](#wake-up-a-machine-given-saved-configuration-name)
    - [List existing configuration names](#list-existing-configuration-names)
    - [Delete a configuration](#delete-a-configuration)
    - [Transferring configurations to another machine](#transferring-configurations-to-another-machine)
- [Set up shell autocomplete](#set-up-shell-autocomplete)
    - [Bash](#bash)
    - [Zsh](#zsh)
    - [Powershell](#powershell)

<!-- /TOC -->


## Why another one?

I couldn't find one that worked and did what I need. Specifically I need:
* A command line utility that works on Mac, Windows and Linux
* Can use saved configurations rather than force me to remember the MAC addresses of the machines I need to wake.
* Ideally, let me manipulate (create, delete, update, list) saved configurations using the same utility.
* Ideally, be open source so I can see what it is doing and know it doesn't do anything nefarious

None of the existing tools I found satisfied these criteria (even without the last two) so I wrote my own.

## Setup

**Pre-requisites**: Python 3.7 or above. No additional packages required.

```bash
pip3 install eg.wakeonlan
```

On Windows, if you get a warning like:
```
WARNING: The script wakeonlan.exe is installed in 
'C:\Users\[username]\AppData\Roaming\Python\Python[VER]\Scripts' which is not on PATH.
```

You can either add this directory to your PATH or run `pip3 install` from Administrator command prompt.

The reason for this message is that Python does not add _per user_ scripts directory to PATH on Windows, only the system-wide one. See [this Python bug](https://bugs.python.org/issue39658)

## Usage


### Wake up a machine given its MAC address XX:XX:XX:XX:XX:XX 

```bash
wakeonlan XX:XX:XX:XX:XX:XX [-a BroadcastAddress] [-p Port]
```

If not specified BroadcastAddress is 255.255.255.255 and Port is 9

### Save wake up configuration to be used later

```bash
wakeonlan --save Name XX:XX:XX:XX:XX:XX [-a BroadcastAddress] [-p Port]
```

Name can be anything. The configuration is saved into `$HOME/.wakeonlan` file in JSON format
--save can be abbreviated as -s

### Wake up a machine given saved configuration name

```bash
wakeonlan Name
```

### List existing configuration names

```bash
wakeonlan --list
```

`--list` can be abbreviated as `-l`

### Delete a configuration

```bash
wakeonlan --delete Name
```

`--delete` can be abbreviated as `-d`

### Transferring configurations to another machine

Saved configurations are stored in `$HOME/.wakeonlan` file (`%USERPROFILE%\.wakeonlan` for Windows users).
Copy this file to another machine into equivalent location to transfer all the configurations.

## Set up shell autocomplete

Autocomplete is supported for `bash`, `zsh` and `powershell`.

### Bash

Add the following to your `~/.bashrc`

```bash
source `wakeonlan --autocomplete-source`
```

### Zsh

Add the following to your `~/.zhrc` (make sure it is *after* the call to `compinit`)

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
2. Find the location of your profile file:
  ```ps
  echo $profile
  ```
3. If it doesn't exist, create it. Then add the following to its content:
  ```ps
  . $(wakeonlan --autocomplete-source)
  ```

