"""Summarize close-range visibility and contact duration in mechreplay/1 casts."""

import argparse
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from bot import Arena


def summarize(path, arena):
    trajectories = defaultdict(list)
    placements = {}
    with gzip.open(path, "rt") as stream:
        header = json.loads(next(stream))
        hz = header["tick_hz"]
        for line in stream:
            frame = json.loads(line)
            for event in frame.get("ev", ()):
                if event["e"] == "death" and event["id"] < 16:
                    placements[event["id"]] = event["place"]
            if "m" not in frame or frame["t"] % hz:
                continue
            visible = set()
            mechs = frame["m"]
            for i, a in enumerate(mechs):
                for b in mechs[i + 1:]:
                    if math.hypot(a[1] - b[1], a[2] - b[2]) >= 100:
                        continue
                    if arena.clear_view([a[1], a[2], a[3] + 7], [b[1], b[2], b[3] + 7]):
                        visible.update((a[0], b[0]))
            for mech in mechs:
                trajectories[mech[0]].append(mech[0] in visible)

    lives = []
    for actor, trace in trajectories.items():
        entered = escaped = 0
        for start, exposed in enumerate(trace):
            if not exposed:
                continue
            if start and (start < 3 or any(trace[start - 3:start])):
                continue
            entered += 1
            window = trace[start:start + 13]
            if any(not any(window[j:j + 3]) for j in range(1, len(window) - 2)):
                escaped += 1
        lives.append((placements.get(actor, 1), len(trace), sum(trace), entered, escaped))
    return lives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", type=Path, nargs="+")
    parser.add_argument("--map-dir", type=Path, default=Path(".cache/mechfight-kit/arena"))
    args = parser.parse_args()
    arena = Arena(args.map_dir)
    lives = [row for path in args.replays for row in summarize(path, arena)]
    for label, group in (
        ("Places 1–8", [r for r in lives if r[0] <= 8]),
        ("Places 9–16", [r for r in lives if r[0] > 8]),
    ):
        if group:
            print(f"{label}: {len(group)} lives, "
                  f"mean time exposed {statistics.mean(r[2] / r[1] for r in group):.1%}, "
                  f"contacts cleared within 12 s {sum(r[4] for r in group)}/{sum(r[3] for r in group)}")


if __name__ == "__main__":
    main()
