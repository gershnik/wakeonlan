# wakeonlan #

Yet another wake-on-lan command line script.

## Why another one?

I couldn't find one that worked and did what I need. Specifically I need:
* A command line utility that works on Mac, Windows and Linux
* That can used saved configurations rather than have me to remember the MAC address of the machines I need to wake.
* Ideally, be open source so I can see what it is doing and know it doesn't do anything nefarious

None of the existing tools satisfied these criteria (even without the last) so I wrote my own.

### Pre-requisites

Python 3.7 or above. No additonal packages required.

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

Name can be anything. The configuration is saved into $HOME/.wakeonlan file in JSON format
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

### Installation

On Unix systems:

* Download `wakeonlan` script
* Execute
    ```bash
    chmod a+x wakeonlan
    sudo cp wakeonlan /usr/local/bin
    ```
Note: the shebang command in the script is `/usr/bin/env python3`. This needs to work on your machine to launch Python 3. This is usually the case for most Unix systems. If your machine has some non-standard configuration you will need to modify the shebang line.

On Windows:

* Download `wakeonlan` script and `wakeonlan.cmd` launcher
* Copy both to a desired directory. 
* If the directory isn't in your PATH already, add it to PATH.

Note:  `wakeonlan.cmd` launcher will attempt to use `py -3` to launch the script if possible and if not fall back on `python`. One of those ways needs to work on your machine to launch Python 3 for this to work. If your machine has some non-standard configuration you will need to modify `wakeonlan.cmd` launcher to deal with it.


