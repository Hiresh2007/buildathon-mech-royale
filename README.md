# Outlast · Mech Royale

Outlast is a Python bot for the Builders arena. It routes through campus using terrain, building footprints and its collision radius. It remembers recently seen equipment, captures uncontested supply drops and looks for cover when wounded. It follows announced supply drops within their travel-time window, prioritizes nearby power-cube clusters, and allows health regeneration when wounded and alone. It uses each equipped weapon's trigger rules and checks the static map before engaging actors in the arena's vision memory.

## Isolated opponents in practice

The official practice field contains 15 house mechs with shared vision. The weakest pursues the entrant first and more join later. This experiment starts from the 4.17 practice build, `7128d38`. While healthy and inside the circle, the controller can hold a useful distance from one isolated rival facing away. It watches for a second nearby rival, recent incoming damage, the next circle deadline, and the late squad. Its current weapon determines the distance it holds. The navigation, supplies and upgrades follow the baseline policy.

The complete controller was compared with the baseline on opening encounters from five public matches, followed by a newly broadcast Top-16 match. It drove its own avatar on the official map while opponents continued their recorded movements. The trials used the standard gun, recorded rival damage when the simulated avatar remained visible, gun reloads, the virtual torso and avatar collision geometry. The sample retained isolated away-facing openings and face-on controls from even-numbered entrant slots. Starts were spaced at least 22 seconds apart per entrant. Each window lasted up to 20 seconds or until elimination.

| Public encounter windows | Baseline direct eliminations | Updated direct eliminations | Baseline / updated entrant deaths |
| --- | ---: | ---: | ---: |
| First five public matches, 73 windows | 18 | 22 | 2 / 2 |
| Held-out Top-16 match, 20 windows | 5 | 7 | 0 / 0 |

The organizers keep the coordinated practice trajectories private. Whole-match tests used the same seeds for both controllers and varied what a house mech does before becoming an active pursuer.

| House behavior | Seeds | Mean placement, baseline → updated | Contestant eliminations | Zone eliminations | Survival seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Nonpursuers follow their current routes | 12 | 2.67 → 4.75 | 2.42 → 3.67 | 0.25 → 1.08 | 143.78 → 164.30 |
| Nonpursuers return fire when hit | 14 | 1.29 → 1.71 | 1.00 → 1.29 | 0.29 → 0.43 | 108.14 → 117.29 |
| Most nonpursuers face a shared sighting and nearby guards can engage | 22 | 2.45 → 2.45 | 1.41 → 1.41 | 1.05 → 1.05 | 149.24 → 151.54 |

NPC-attributed squad eliminations averaged zero in these three settings. Only the official practice run establishes the competition score. The synthetic decision tests run with `python3 -m unittest test_duel`.

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
