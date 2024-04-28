# wakeonlan #

Yet another wake-on-lan command line script.

## Why another one?

I couldn't find one that worked and did what I need. Specifically I need:
* A command line utility that works on Mac, Windows and Linux
* Can use saved configurations rather than force me to remember the MAC addresses of the machines I need to wake.
* Ideally, let me manipulate (create, delete, update, list) saved configurations using the same utility.
* Ideally, be open source so I can see what it is doing and know it doesn't do anything nefarious

None of the existing tools I found satisfied these criteria (even without the last two) so I wrote my own.

### Pre-requisites

Python 3.7 or above. No additional packages required.

### Installation

```bash
pip3 install eg.wakeonlan
```

### Usage


#### Wake up a machine given its MAC address XX:XX:XX:XX:XX:XX 

```bash
wakeonlan XX:XX:XX:XX:XX:XX [-a BroadcastAddress] [-p Port]
```

If not specified BroadcastAddress is 255.255.255.255 and Port is 9

#### Save wake up configuration to be used later

```bash
wakeonlan --save Name XX:XX:XX:XX:XX:XX [-a BroadcastAddress] [-p Port]
```

Name can be anything. The configuration is saved into `$HOME/.wakeonlan` file in JSON format
--save can be abbreviated as -s

#### Wake up a machine given saved configuration name

```bash
wakeonlan Name
```

#### List existing configuration names

```bash
wakeonlan --list
```

`--list` can be abbreviated as `-l`

#### Delete a configuration

```bash
wakeonlan --delete Name
```

`--delete` can be abbreviated as `-d`

### Transferring configurations to another machine

Saved configurations are stored in `$HOME/.wakeonlan` file (`%USERPROFILE%\.wakeonlan` for Windows users).
Copy this file to another machine into equivalent location to transfer all the configurations.




