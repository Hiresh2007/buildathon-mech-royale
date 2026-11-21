# Outlast · Mech Royale

Outlast is a Python bot for the Builders arena. It routes through campus using terrain, building footprints and its collision radius. It remembers recently seen equipment, captures uncontested supply drops and looks for cover when wounded. It follows announced supply drops within their travel-time window, prioritizes nearby power-cube clusters, and allows health regeneration when wounded and alone. It uses each equipped weapon's trigger rules and checks the static map before engaging actors in the arena's vision memory.

## Official practice result

Builders scored this controller **4.63 placement points** across 48 practice matches and selected it for the final under receipt `BB-1E7E60FE`. It builds on the 4.19 bot’s behavior around isolated opponents. When carrying two weapons, it can swap its secondary for a stronger nearby pickup. Across 22 independent paired local matches, that change raised mean placement points from 4.73 to 5.50. The Dockerfile uses the exact controller and game interface from the [scored commit](https://github.com/Hiresh2007/buildathon-mech-royale/commit/dee82d2cffc63e27cb975cc02c2dee8268233648).

Run `python3 -m unittest test_duel test_equipment` for the encounter and equipment decision checks. The replay drills below document earlier controller revisions.

## Early upgrades and passive repair in `2cb1019`

Starting from the official 4.17 policy at `7128d38`, Outlast goes for its first cube when it can reach and open a nearby crate before a rival gets there. It picks the crate using the time to walk into collection range and finish opening it. When wounded and already close to resuming passive repair, it can pass up an interaction until it recovers. Urgent circle movement and nearby recovery items retain priority.

Across 64 historical spawn positions from four public spectator matches, Outlast earned its first cube inside 25 seconds on 48 starts. The 4.17 policy did so on 37. Its capped mean time to this upgrade fell from 16.0 to 11.8 seconds. The historical players followed their recorded paths.

| Fresh full-match comparison | `7128d38` | Early upgrade and repair |
| --- | ---: | ---: |
| Higher-pressure grounded model, 18 seeds | 1.89 | 2.44 |
| Medium-pressure flight model, 18 seeds | 4.22 | 4.78 |
| Lower-pressure grounded model, 18 seeds | 5.61 | 7.28 |

The 54 paired simulations averaged 19.3 additional survival seconds. Across 36 calibration seeds, the same referee ranked the four previously scored policies in a different order from the official house squad. Only the organizer's 48 practice matches provide an official score.

## Movement near other mechs in `1825925`

The official run for `1825925` scored 4.02. That revision built on the official 4.17 entry, `7128d38`. When nearby rivals close in, Outlast compares walkable map cells and uses their separation from up to four observed rivals to choose a destination. It accounts for the next circle while choosing the cell. Supply collection, healing and urgent circle returns retain their priorities from that entry.

Across 48 lives in three public matches, the bottom eight finishers in each match spent a mean 50.9% of their lives within 100 m and unobstructed sight of another mech. The top eight averaged 31.7%. After entering that range, the two groups broke visibility for three consecutive seconds within the following 12 s on 12 of 45 and 64 of 116 occasions, respectively. The measurement samples each second and checks terrain and solid geometry. [Organizer's public mechanics replay](https://play.joinbuilders.org/replays/mechanics-v2-16.jsonl.gz)

```sh
python3 replay_exposure.py /path/to/match.jsonl.gz
```

| Local measurement | Official 4.17 entry | `1825925` |
| --- | ---: | ---: |
| Contacts cleared within 12 s on 16 held-out replay starts | 10/16 | 15/16 |
| Mean exposure over those 12 s | 6.33 s | 4.02 s |
| Mean placement points, eight high-pressure modeled matches with flight | 3.00 | 5.38 |
| Mean placement points, twelve fresh modeled matches with flight and 10 Hz decisions | 5.67 | 6.17 |
| Mean placement points, twelve lower-pressure modeled matches with grounded movement | 8.08 | 6.83 |

The contact check used all 16 eligible starts in the opening 53.7 s of a fourth public spectator match, seed 2335036466. Archival rivals follow their recorded paths. The full-match model approximates squad pursuit and starts idle rivals toward the next circle based on their travel time. Only the official 48-game evaluation measures the submitted placement score.

## Opening equipment and circle returns in `fb5d538`

The official run for `fb5d538` scored 3.96. This revision built on `7128d38`, which scored 4.17. While the second slot is empty, the bot searches the full sensor arc when alone, remembers visible floor equipment and spends rechargeable movement energy to reach it. On an urgent return to the circle, it spends energy in grounded bursts. Airborne boost applies upward thrust in this game. The local checks use that distinction when advancing the mech.

| Local measurement | `7128d38` | `5b8d740` | Current |
| --- | ---: | ---: | ---: |
| Second slot filled by 22 s | 24/48 | 26/48 | 34/48 |
| Mean seconds to an equipped second slot, capped at 22 s | 13.51 | 12.95 | 10.16 |
| Circle detours completed before their seeded deadline | 50/64 | 51/64 | 55/64 |
| Mean seconds to reenter the circle, capped at 36 s | 14.59 | 13.45 | 12.37 |

The opening comparison uses all 16 spawn poses in each of three public casts, their initial loot and crate locations, recorded rival movements and recorded claims on floor equipment. Each policy receives a 10 Hz observation and moves at 20 Hz using ground and airborne acceleration. The check models vision wedges and map geometry. The original opponents follow their recorded paths. The official 48-game practice run measures placement against a reacting squad. [Organizer mechanics replay](https://play.joinbuilders.org/replays/mechanics-v2-16.jsonl.gz)

The circle comparison uses 64 connected ground routes with a detour on the official map. It advances the same starting positions and energy at 20 Hz with the official jump, jet, recharge and boost values. The official protocol checker answered 300/300 observations on time for this policy, with a 4.8 ms maximum on the development machine.

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

### Full-match placement and recovery in `5b8d740`

The official run for `5b8d740` scored 4.04. The practice squad shares vision, starts with one active hunter, and adds more as its members are eliminated. That revision values a cube pile by how many useful cubes it contains and whether it unlocks an upgrade. It considers another visible mech's time to reach the pile. A wounded mech compares the remaining clock on an uncontested restorative drop against its passive repair time. Ground collectibles on a hillside stay eligible when both endpoints are near the terrain surface. The four-metre vertical limit still applies at pickup. Short navigation segments check the mech's expanded footprint and the location of the next turn. [Practice scoring rules](https://www.joinbuilders.org/buildathon/tracks/builders)

The local placement model runs all six announced circles, fifteen friendly-to-one-another house actors, HP repair, energy, collectible growth, upgrade offers and restorative drops. It approximates the number of active house opponents, their movement and contact damage. The damage rates come from the organizer's public free-for-all replay. The model uses grounded movement and a simplified neutral pickup layout. The official 48-match practice run determines leaderboard placement. [Organizer replay](https://play.joinbuilders.org/replays/mechanics-v2-16.jsonl.gz)

The following commands reproduce the three conditions used for the 36-seed comparison. Each policy sees the same 12 starts in a condition. The third run uses the official 10 Hz decision cadence. The burst option turns average incoming damage into discrete 45-HP events with matched random draws. The separate landed-drop drill starts with an injured mech, nearby loose cubes, an available supply and a seeded collection deadline.

```sh
git show 7128d38:bot.py > /tmp/outlast-before-recovery.py
git show 5b8d740:bot.py > /tmp/outlast-recovery.py
python3 placement_drill.py --bots /tmp/outlast-before-recovery.py /tmp/outlast-recovery.py --seed 201377 --count 12 --pressure 0.85
python3 placement_drill.py --bots /tmp/outlast-before-recovery.py /tmp/outlast-recovery.py --seed 218149 --count 12 --pressure 1.65 --burst
python3 placement_drill.py --bots /tmp/outlast-before-recovery.py /tmp/outlast-recovery.py --seed 227009 --count 12 --pressure 1.2 --decision-step 0.1 --burst
python3 landed_drop_drill.py --bots /tmp/outlast-before-recovery.py /tmp/outlast-recovery.py
```

| Measurement | Previous official entry (`7128d38`) | Updated |
| --- | ---: | ---: |
| Mean modeled placement points, 36 paired seeds | 8.08 | 9.50 |
| Mean simulated survival | 202.18 s | 223.53 s |
| Mean zone HP lost | 321.37 | 183.40 |
| Mean cubes collected over a match | 8.14 | 10.94 |
| Captures before a seeded deadline, 48 landed-drop starts | 17 | 41 |
| Cubes collected, established 72-start reward drill | 514 | 540 |
| Upgrade offers in that drill | 213 | 221 |
| Announced supplies captured in that drill | 71/72 | 71/72 |

The updated bot placed higher on 17 paired seeds, tied on 13 and placed lower on six. On the official protocol replay it answered 300/300 observations within the 50 ms deadline. The previous entry's official practice score was 4.17.
