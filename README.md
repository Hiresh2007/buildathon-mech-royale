# Outlast · Mech Royale

Outlast is a Python bot for the Builders arena. It routes through campus using terrain, building footprints and its collision radius. It remembers recently seen equipment, captures uncontested supply drops and looks for cover when wounded. It uses each equipped weapon's trigger rules and checks the static map before engaging actors in the arena's vision memory.

## Run the replay check

```sh
make check
```

Python 3.9+ and Make are sufficient. The target downloads the organizer's versioned-by-checksum kit into `.cache/`. It replays 300 observations and verifies action format, timing, stale observations and shutdown. Match placement is measured by the live practice scorer.

With Docker running, use `make check-docker` to repeat the check on linux/amd64 under the CPU, memory, filesystem and user limits. Publish this directory as its own public repository with the Dockerfile at the root. [Track and submission form](https://www.joinbuilders.org/buildathon/tracks/builders)

## Compare local behavior

After `make check` has installed the kit, run the seeded drills and the recorded-motion check with either policy.

```sh
git show d7bad9a:bot.py > /tmp/outlast-reference.py
python3 benchmark.py --bot /tmp/outlast-reference.py
python3 benchmark.py
```

| Local measurement | Original | Current |
| --- | ---: | ---: |
| Uncontested supply drops captured within 28 s | 4/32 | 28/32 |
| Mean time behind cover, starting wounded, over 28 s | 8.15 s | 10.50 s |
| Aim overlapping the opponent at its later recorded position | 45/103 | 53/103 |

The two movement drills use seeds 1001–1032, held out from development. They run grounded walking on the official campus map. The cover drill uses one stationary observer. The aim check uses ordinary gun range and the opponent's subsequent positions in the organizers' single recorded stream. It measures the commanded direction before weapon spread and torso slew. The official scorer measures placement over 48 games against the full house squad.

## Credits

`bot.py` is the team's strategy. The standard-library protocol wrapper in `mechfight.py` comes from the official Python kit. The checker, recorded match stream and arena map also come from the organizers. [Official kit](https://www.joinbuilders.org/buildathon/tracks/builders/files/mechfight-kit.tar.gz)
