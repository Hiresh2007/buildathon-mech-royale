"""Seeded collection drills using the organizer's game map, timing and reward rules."""

import argparse
import copy
import gzip
import json
import math
import random
from pathlib import Path

from benchmark import load_bot, slew
from bot import Arena


def walk(arena, me, action, cfg, dt):
    # Model the kit's grounded walk, obstacle footprint and axis-wise wall slide.
    for axis, move in enumerate(action["move"]):
        velocity = slew(
            me["vel"][axis], cfg["walk_speed"] * move, dt * cfg["ground_accel"]
        )
        pos = list(me["pos"])
        pos[axis] += dt * velocity
        tr = arena.terrain
        ix, iy = [
            round((value - tr[key]) / tr["step"])
            for value, key in zip(pos[:2], ("minX", "minY"))
        ]
        if not (0 <= ix < tr["nx"] and 0 <= iy < tr["ny"]):
            continue
        z = arena.heights[iy * tr["nx"] + ix] * tr["scale"]
        r = cfg["radius"]
        if abs(z - pos[2]) > cfg["step_up"] or any(
            arena.blocked(pos[0] + dx, pos[1] + dy, z, cfg["height"])
            for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))
        ):
            velocity = 0
        else:
            pos[2] = z
            me["pos"] = pos
        me["vel"][axis] = velocity


def position(arena, cell):
    return [cell[0] * arena.step, cell[1] * arena.step, arena.ground[cell]]


def run(bot_type, hello, template, arena, seed, far):
    rng = random.Random(seed)
    center = template["zone"]["next_center"]
    inside = [
        k for k in arena.ground if math.dist(position(arena, k)[:2], center) < 330
    ]
    while True:
        start = rng.choice(inside)
        if far:
            angle, radius = rng.random() * 2 * math.pi, rng.uniform(20, 34)
            end = (
                start[0] + round(radius * math.cos(angle)),
                start[1] + round(radius * math.sin(angle)),
            )
            if (
                end in arena.ground
                and math.dist(position(arena, end)[:2], center) < 330
            ):
                path = arena.route(position(arena, start), position(arena, end))
                if path and math.dist(path[-1], position(arena, end)[:2]) < 1:
                    break
        else:
            near = [
                k
                for k in arena.ground
                if 1 <= math.dist(k, start) <= 3
                and abs(arena.ground[k] - arena.ground[start]) <= 3
            ]
            if len(near) >= 7:
                break
    obs = copy.deepcopy(template)
    cfg = hello["config"]
    start_t = cfg["drops"]["times"][0] if far else 8.0
    for k in (
        "mechs",
        "crates",
        "cubes",
        "pickups",
        "sounds",
        "events",
        "projectiles",
        "beams",
        "drops",
    ):
        obs[k] = []
    obs["offer"] = None
    me, rules = obs["self"], cfg["mech"]
    me.update(
        pos=position(arena, start),
        vel=[0, 0, 0],
        hp=rules["hp"] * 0.7,
        max_hp=rules["hp"],
        cubes=0,
        energy=100,
        grounded=True,
        in_zone=True,
    )
    obs["zone"].update(
        center=center,
        radius=400,
        next_center=center,
        next_radius=380,
        shrink_start=start_t + 65,
        shrink_end=start_t + 100,
    )
    if far:
        drop_cfg = cfg["drops"]
        drop = dict(
            id=20000,
            pos=position(arena, end),
            radius=drop_cfg["radius"],
            capture_s=drop_cfg["capture_s"],
            progress=0,
            lands_in=drop_cfg["fall_s"],
            holder=None,
        )
        obs["drops"] = [drop]
    else:
        areas = rng.sample(near, 4)
        counts = [1, 1, rng.randint(2, 4), rng.randint(2, 4)]
        for site, count in zip(areas, counts):
            xyz = position(arena, site)
            for _ in range(count):
                obs["cubes"].append(
                    dict(
                        id=5000 + len(obs["cubes"]),
                        pos=[
                            xyz[0] + rng.uniform(-0.5, 0.5),
                            xyz[1] + rng.uniform(-0.5, 0.5),
                            xyz[2],
                        ],
                    )
                )
    bot = bot_type(hello)
    tick_hz, decide = cfg["match"]["tick_hz"], cfg["match"]["decide_every"]
    dt = 1 / tick_hz
    duration = 42 if far else 5
    for tick in range(round(duration * tick_hz)):
        now = tick / tick_hz
        if far:
            drop["lands_in"] = max(0, cfg["drops"]["fall_s"] - now)
        if tick % decide == 0:
            obs.update(t=start_t + now, tick=tick)
            action = bot.act(obs)
        walk(arena, me, action, rules, dt)
        if far:
            if (
                not drop["lands_in"]
                and math.dist(me["pos"][:2], drop["pos"][:2]) <= drop["radius"]
            ):
                drop["holder"] = me["id"]
                drop["progress"] += dt
                if drop["progress"] >= drop["capture_s"]:
                    return 1
            else:
                drop["holder"], drop["progress"] = None, 0
        else:
            remaining = [
                c
                for c in obs["cubes"]
                if math.dist(me["pos"][:2], c["pos"][:2])
                > cfg["cubes"]["pickup_radius"]
                or abs(me["pos"][2] - c["pos"][2]) > 4
            ]
            acquired = len(obs["cubes"]) - len(remaining)
            me["cubes"] += acquired
            me["hp"] += acquired * rules["hp"] * cfg["cubes"]["hp_per_cube"]
            obs["cubes"] = remaining
    return 0 if far else me["cubes"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(".cache/mechfight-kit"))
    parser.add_argument("--bot", type=Path, default=Path("bot.py"))
    parser.add_argument("--seed", type=int, default=62001)
    parser.add_argument("--count", type=int, default=64)
    args = parser.parse_args()
    with gzip.open(args.kit / "check/stream.jsonl.gz") as inp:
        hello, template = json.loads(next(inp)), json.loads(next(inp))
    directory = str((args.kit / "arena").resolve())
    hello["map"]["dir"] = directory
    arena, bot_type = Arena(directory), load_bot(args.bot, directory)
    cubes = [
        run(bot_type, hello, template, arena, s, False)
        for s in range(args.seed, args.seed + args.count)
    ]
    drops = [
        run(bot_type, hello, template, arena, s, True)
        for s in range(args.seed, args.seed + args.count)
    ]
    print(f"Cubes collected in five seconds {sum(cubes)} across {len(cubes)} starts")
    print(
        f"Announced distant supply drops captured within 42 seconds {sum(drops)}/{len(drops)}"
    )


if __name__ == "__main__":
    main()
