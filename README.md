# Lavalink-Updater
Py script to update and launch Lavalink.jar

***

```
usage: Lavalink.py [-h] [-c] [-l LAVALINK_VERSION] [-y YTS_VERSION] [-f] [-d] [-s] [-o] [-g]
                   [-r {kill,ignore,quit,ask}]

Lavalink.py - a py script to update and launch Lavalink.jar

options:
  -h, --help            show this help message and exit
  -c, --check-updates   only report the latest Lavalink and YouTube-Source versions (overrides all but --help)
  -l LAVALINK_VERSION, --lavalink-version LAVALINK_VERSION
                        update Lavalink.jar to the passed version tag instead of "latest" if it exists (requires
                        --force[-if-different] if passing an older version)
  -y YTS_VERSION, --yts-version YTS_VERSION
                        update YouTube-Source to the passed version tag instead of "latest" if it exists (requires
                        --force[-if-different] if passing an older version)
  -f, --force           force Lavalink.jar and YouTube-Source updates (overrides --force-if-different)
  -d, --force-if-different
                        force Lavalink.jar and YouTube-Source updates only if the local and remote versions are
                        different
  -s, --skip-updates    skip update checks (overrides --force)
  -o, --only-update     only update, don't start Lavalink (overrides --skip-updates)
  -g, --skip-git        GitHub self updates
  -r {kill,ignore,quit,ask}, --handle-running {kill,ignore,quit,ask}
                        how to handle detected currently running Lavalink.jar instances
```
