"""Test landed supply captures before seeded deadlines, with ground pickups nearby."""

import argparse
import copy
import gzip
import json
import math
import random
from pathlib import Path

from benchmark import load_bot
from bot import Arena
from reward_drill import position, walk


def landed_race(bot_type, hello, template, arena, cells, seed):
    cfg = hello["config"]
    rules = cfg["mech"]
    rng = random.Random(seed)
    while True:
        mepos = position(arena, rng.choice(cells))
        drop = position(arena, rng.choice(cells))
        dist = math.dist(mepos[:2], drop[:2])
        route = arena.route(mepos, drop)
        if 90 < dist < 235 and route and math.dist(route[-1], drop[:2]) < 2:
            break
    obs = copy.deepcopy(template)
    me = obs["self"]
    me.update(
        pos=mepos,
        vel=[0, 0, 0],
        hp=rng.uniform(0.28, 0.76) * 1400,
        max_hp=1400,
        cubes=rng.randrange(5),
        energy=100,
        grounded=True,
        in_zone=True,
    )
    for k in (
        "sounds",
        "events",
        "mechs",
        "crates",
        "projectiles",
        "beams",
        "pickups",
        "cubes",
        "drops",
    ):
        obs[k] = []
    obs["offer"] = None
    zone = (mepos[0] * 0.5 + drop[0] * 0.5, mepos[1] * 0.5 + drop[1] * 0.5)
    obs["zone"].update(
        center=zone, next_center=zone, radius=340, next_radius=290, shrink_start=160, shrink_end=200
    )
    d = dict(id=20000, pos=drop, radius=8.0, capture_s=4.0, lands_in=0.0, holder=None, progress=0.0)
    obs["drops"] = [d]
    free_sites = [
        c
        for c in cells
        if 22 < math.dist(position(arena, c)[:2], mepos[:2]) < 85
        and abs(position(arena, c)[2] - mepos[2]) < 4
    ]
    for i, node in enumerate(rng.sample(free_sites, min(3, len(free_sites)))):
        obs["cubes"].append(dict(id=5000 + i, pos=position(arena, node)))
    max_time = rng.uniform(16, 29)
    dt = 0.05
    actor = bot_type(hello)
    last_spent = last_damage = 0.0
    for tick in range(round(30 / dt)):
        t = tick * dt
        if t >= max_time:
            obs["drops"] = []
        if (tick // 60) % 2 == 0 and tick % 60 == 0 and seed % 2 == 0:
            me["hp"] -= 55
            last_damage = t
        if t - last_damage >= 5:
            me["hp"] = min(me["max_hp"], me["hp"] + 45 * dt)
        if tick % 2 == 0:
            obs.update(t=98 + t, tick=tick)
            action = actor.act(obs)
        m = dict(rules)
        if action.get("boost") and me["energy"] >= rules["boost_drain"] * dt:
            m["walk_speed"] = rules["boost_speed"]
            me["energy"] -= rules["boost_drain"] * dt
            last_spent = t
        elif t - last_spent >= rules["energy_regen_delay"]:
            me["energy"] = min(100, me["energy"] + rules["energy_regen"] * dt)
        walk(arena, me, action, m, dt)
        near = [
            item
            for item in obs["cubes"]
            if math.dist(me["pos"][:2], item["pos"][:2]) < 3.5
            and abs(me["pos"][2] - item["pos"][2]) <= 4
        ]
        for item in near:
            obs["cubes"].remove(item)
            me["cubes"] += 1
            me["hp"] += 56
            me["max_hp"] += 56
        if obs["drops"] and math.dist(me["pos"][:2], drop[:2]) < 8:
            d["holder"] = me["id"]
            d["progress"] += dt
            if d["progress"] >= d["capture_s"]:
                return True
        else:
            d["holder"] = None
            d["progress"] = 0
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(".cache/mechfight-kit"))
    parser.add_argument("--bots", type=Path, nargs="+", default=[Path("bot.py")])
    parser.add_argument("--seed", type=int, default=249401)
    parser.add_argument("--count", type=int, default=48)
    args = parser.parse_args()
    directory = str((args.kit / "arena").resolve())
    with gzip.open(args.kit / "check/stream.jsonl.gz") as stream:
        hello, template = json.loads(next(stream)), json.loads(next(stream))
    hello["map"]["dir"] = directory
    arena = Arena(directory)
    cells = list(arena.ground)
    for path in args.bots:
        bot_type = load_bot(path, directory)
        captures = sum(
            landed_race(bot_type, hello, template, arena, cells, seed)
            for seed in range(args.seed, args.seed + args.count)
        )
        print(f"{path.name} captured {captures}/{args.count} landed supplies", flush=True)


if __name__ == "__main__":
    main()
