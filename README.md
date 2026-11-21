# Outlast · Mech Royale

Outlast is a Python bot for the Builders arena. It routes through campus using terrain, building footprints and its collision radius. It remembers recently seen equipment, captures uncontested supply drops and looks for cover when wounded. It follows announced supply drops within their travel-time window, prioritizes nearby power-cube clusters, and allows health regeneration when wounded and alone. It uses each equipped weapon's trigger rules and checks the static map before engaging actors in the arena's vision memory.

## Visible portion of an arena avatar

The arena tracks mechs when their center or upper body is visible. The 4.17 practice build, `7128d38`, aims at the center and can skip an avatar standing behind a low ledge. This experiment checks a second point at 85% of the avatar's current height when the center is blocked. Cube growth scales both points.

Across 118 encounters from four current public matches, both complete controllers followed the same archived movement with one opposing avatar. Each observed avatar’s encounter starts were separated by at least 38 seconds. The original controller eliminated 21 opponents and the updated controller eliminated 22. Each lost its own avatar three times. The gun, reload clock, visibility memory, torso movement and opponents' later recorded positions determined the outcome. Public broadcasts contain independent teams or house lobbies. The private practice scorer uses a coordinated weakest-first squad.

A subsequently broadcast Top-16 showdown supplied 33 held-out encounters. Both controllers recorded one elimination and survived all 33 windows. The updated controller registered 373 projected hits and 18,251 damage, compared with 356 hits and 17,371 damage for the original. The recorded avatars followed their historical paths.

| Whole-squad proxy, mean per match | Original | Updated |
| --- | ---: | ---: |
| Placement points, 20 seeds | 4.15 | 4.25 |
| Contestant-attributed eliminations | 2.90 | 3.00 |
| Zone eliminations | 1.25 | 1.25 |
| NPC eliminations | 0.00 | 0.00 |
| Seconds survived | 166.58 | 170.14 |
| Placement points, 12 higher-pressure seeds | 3.33 | 3.33 |

Across six shared seeds the model’s ranking of six earlier official builds had a Spearman correlation of −0.35 with the practice scores. The organizers' private practice scorer measures the official placement result. Run `python3 -m unittest test_visible_avatar` for the open, partially occluded and fully occluded avatar cases.

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

| Local measurement | d7bad9a | dc0488c |
| --- | ---: | ---: |
| Uncontested supply drops captured within 28 s | 4/32 | 28/32 |
| Mean time behind cover, starting wounded, over 28 s | 8.15 s | 10.50 s |
| Aim overlapping the opponent at its later recorded position | 45/103 | 53/103 |

The two movement drills use seeds 1001–1032, held out from development. They run grounded walking on the official campus map. The cover drill uses one stationary observer. The aim check uses ordinary gun range and the opponent's subsequent positions in the organizers' single recorded stream. It measures the commanded direction before weapon spread and torso slew. The official scorer measures placement over 48 games against the full house squad.

### Supply and power-cube collection

The previous official entry at `dc0488c` scored 3.81 placement points over 48 games. The competition awards `16 - place` per game. The current policy uses the reported time until a drop lands, the mech's walk speed, the amount of capture time already earned and the proximity of automatic cube pickups.

```sh
git show dc0488c:bot.py > /tmp/outlast-placement-reference.py
python3 reward_drill.py --bot /tmp/outlast-placement-reference.py
python3 reward_drill.py
```

| Measurement over 64 held-out starts | dc0488c | Updated |
| --- | ---: | ---: |
| Power cubes collected within five seconds | 384 | 405 |
| Announced drops captured within 42 seconds from 160–272 m away | 16 | 58 |

The two drills run each controller through its normal observation entry point on the official map, with grounded walking, collisions, pickup radii and capture clocks. They use fixed seeds 62001–62064. They exclude other entrants and measure collectible outcomes. The official practice scorer measures placement against the full house squad.

The boosted drill also applies the official grounded boost speed, energy drain and recharge delay, and cube-driven body growth and HP. Surplus energy is spent on actual power cubes and announced restorative drops. On a fresh set of 72 starts, the previous policy collected 483 cubes, unlocked 203 upgrade offers and captured 70 drops. The updated policy collected 514 cubes, unlocked 213 offers and captured 71 drops.

```sh
git show eaec5e2:bot.py > /tmp/outlast-energy-reference.py
python3 reward_drill.py --boost --seed 88001 --count 72 --bot /tmp/outlast-energy-reference.py
python3 reward_drill.py --boost --seed 88001 --count 72
```

## Credits

`bot.py` is the team's strategy. The standard-library protocol wrapper in `mechfight.py` comes from the official Python kit. The checker, recorded match stream and arena map also come from the organizers. [Official kit](https://www.joinbuilders.org/buildathon/tracks/builders/files/mechfight-kit.tar.gz)
