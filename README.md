# Outlast · Mech Royale

Outlast is a Python bot for the Builders arena. It plans routes to the next circle using a navigation grid built from the terrain and building footprints. It seeks power cubes and equipment when the route is clear and prioritizes survival upgrades. Its actions use the map and observations provided to every bot.

## Run the replay check

```sh
make check
```

Python 3.9+ and Make are sufficient. The target downloads the organizer's versioned-by-checksum kit into `.cache/`. It replays 300 observations and verifies action format, timing, stale observations and shutdown. Match placement is measured by the live practice scorer.

With Docker running, use `make check-docker` to repeat the check on linux/amd64 under the CPU, memory, filesystem and user limits. Publish this directory as its own public repository with the Dockerfile at the root. [Track and submission form](https://www.joinbuilders.org/buildathon/tracks/builders)

## Credits

`bot.py` is the team's strategy. The standard-library protocol wrapper in `mechfight.py` comes from the official Python kit. The checker, recorded match stream and arena map also come from the organizers. [Official kit](https://www.joinbuilders.org/buildathon/tracks/builders/files/mechfight-kit.tar.gz)
