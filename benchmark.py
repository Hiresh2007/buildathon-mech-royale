"""Reproducible mechfight/1 drills and an open-loop check on the kit's real motion."""
import argparse
import bisect
import copy
import gzip
import importlib.util
import json
import math
import random
from pathlib import Path

from bot import Arena


def load_bot(path, map_directory):
    spec = importlib.util.spec_from_file_location("contestant", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Cache only this policy's own navigation representation. The referee uses a
    # separately loaded map and every round creates a fresh Bot with fresh memory.
    arena = module.Arena(map_directory)
    module.Arena = lambda _: arena
    return module.Bot


def slew(current, desired, limit, is_yaw=False):
    error = math.remainder(desired - current, 2 * math.pi) if is_yaw else desired - current
    return current + min(limit, max(-limit, error))


def movement_drill(bot_type, hello, arena, template, seed, cover=False):
    # Start on two connected cells on the real map. The drop lands in the next
    # circle. It awards full HP, energy and 3 cubes after four seconds alone.
    rng = random.Random(seed)
    center = template["zone"]["next_center"]
    cells = [c for c in arena.ground
             if math.dist((c[0] * arena.step, c[1] * arena.step), center) < 300]
    while True:
        source = rng.choice(cells)
        dest = (source[0] + rng.randint(-12, 12), source[1] + rng.randint(-12, 12))
        if dest in arena.ground and 6 <= math.dist(source, dest) <= 13:
            def position(cell):
                return [cell[0] * arena.step, cell[1] * arena.step, arena.ground[cell]]
            start, end = position(source), position(dest)
            path = arena.route(start, end)
            valid = path and math.dist(path[-1], end[:2]) < 1
            if valid and cover:
                valid = arena.clear_view([*end[:2], end[2] + 7], [*start[:2], start[2] + 7.65])
            if valid:
                break
    obs = copy.deepcopy(template)
    bot = bot_type(hello)
    for k in ("mechs", "crates", "cubes", "pickups", "sounds", "events", "projectiles", "beams"):
        obs[k] = []
    config = hello["config"]
    dcfg, rules = config["drops"], config["mech"]
    landing = rng.uniform(1, 16)
    obs["drops"] = [dict(id=20000, pos=end, radius=dcfg["radius"], capture_s=dcfg["capture_s"],
                         progress=0, holder=None, lands_in=landing)]
    me = obs["self"]
    me.update(pos=start, vel=[0, 0, 0], aim=[rng.uniform(-math.pi, math.pi), 0],
              hp=rules["hp"] * (0.55 if seed % 2 else 1), max_hp=rules["hp"], energy=rules["energy"])
    if cover:
        obs["drops"] = []
        me["hp"] = rules["hp"] * 0.40
        hunter = {"id": 12, "kind": "mech", "pos": end, "vel": [0, 0, 0], "hp": rules["hp"],
                  "max_hp": rules["hp"], "cubes": 0, "aim": [0, 0], "weapons": ["gun"], "charging": False}
    protected = 0
    last_seen = 0
    dt = 1 / config["match"]["tick_hz"]
    decision_ticks = config["match"]["decide_every"]
    for tick in range(round(28 / dt)):
        now = tick * dt
        if cover:
            visible = arena.clear_view([*end[:2], end[2] + rules["muzzle_height"]],
                                       [*me["pos"][:2], me["pos"][2] + rules["height"] * 0.85])
            if visible:
                last_seen = now
            else:
                protected += dt
            obs["mechs"] = [hunter] if now - last_seen <= config["vision"]["memory_s"] else []
        else:
            drop = obs["drops"][0]
            drop["lands_in"] = max(0, landing - now)
        if tick % decision_ticks == 0:
            obs.update(t=now, tick=tick)
            action = bot.act(obs)
        speed = rules["walk_speed"]  # The drill isolates grounded walking and capture.
        for axis in (0, 1):
            vel = slew(me["vel"][axis], speed * action.get("move", [0, 0])[axis], rules["ground_accel"] * dt)
            pos = me["pos"].copy()
            pos[axis] += dt * vel
            terrain = arena.terrain
            col = round((pos[0] - terrain["minX"]) / terrain["step"])
            row = round((pos[1] - terrain["minY"]) / terrain["step"])
            if not (0 <= col < terrain["nx"] and 0 <= row < terrain["ny"]):
                continue
            ground = arena.heights[row * terrain["nx"] + col] * terrain["scale"]
            if abs(ground - pos[2]) > rules["step_up"]:
                continue
            if any(arena.blocked(pos[0] + x, pos[1] + y, ground, rules["height"])
                   for x, y in ((0, 0), (2.5, 0), (-2.5, 0), (0, 2.5), (0, -2.5))):
                vel = 0
            else:
                pos[2] = ground
                me["pos"] = pos
            me["vel"][axis] = vel
        aim = action.get("aim", me["aim"])
        me["aim"] = [slew(me["aim"][0], aim[0], dt * rules["turn_rate"], True),
                     slew(me["aim"][1], aim[1], dt * rules["pitch_rate"])]
        if cover:
            continue
        if not drop["lands_in"] and math.dist(me["pos"][:2], end[:2]) <= drop["radius"]:
            drop["holder"] = me["id"]
            drop["progress"] += dt
            if drop["progress"] >= drop["capture_s"]:
                return True
        else:
            drop["holder"], drop["progress"] = None, 0
    return protected if cover else False


def recorded_motion(bot_type, hello, arena, frames):
    # For the recorded trajectory, test whether a commanded aim would cross a
    # visible moving avatar's in-game cylinder at its subsequent observed location.
    # This scores commanded aim only; it cannot infer game placement or damage.
    bot = bot_type(hello)
    cfg = hello["config"]
    times = [o["t"] for o in frames]
    hits = opportunities = 0
    for frame in frames:
        action = bot.act(frame)
        me = frame["self"]
        enemies = [a for a in frame["mechs"] if a["kind"] == "mech"]
        if len(enemies) != 1:
            continue
        enemy = enemies[0]
        size = 1 + cfg["cubes"]["size_per_cube"] * enemy.get("cubes", 0)
        radius = cfg["mech"]["radius"] * size
        height = cfg["mech"]["height"] * size
        origin = me["pos"].copy()
        origin[2] += me["stats"]["muzzle_height"]
        center = enemy["pos"].copy()
        center[2] += height / 2
        distance = math.dist(origin, center)
        gun = cfg["weapons"]["gun"]
        if distance > gun["range"] or not arena.clear_view(origin, center):
            continue
        arrival = frame["t"] + max(0, distance - me["stats"]["radius"] - 0.5) / gun["speed"]
        j = bisect.bisect_left(times, arrival)
        if not 0 < j < len(frames) or times[j] - times[j - 1] > 0.11:
            continue
        pair = [next((a["pos"] for a in f["mechs"] if a["id"] == enemy["id"]), None)
                for f in frames[j - 1:j + 1]]
        if any(p is None for p in pair):
            continue
        fraction = (arrival - times[j - 1]) / (times[j] - times[j - 1])
        x, y, z = [a + (b - a) * fraction for a, b in zip(*pair)]
        opportunities += 1
        if "aim" not in action:
            continue
        yaw, pitch = action["aim"]
        dx, dy = x - origin[0], y - origin[1]
        along = dx * math.cos(yaw) + dy * math.sin(yaw)
        side = dx * math.sin(yaw) - dy * math.cos(yaw)
        at_z = origin[2] + along * math.tan(pitch) - z
        hits += along > 0 and abs(side) <= radius and 0 <= at_z <= height
    return hits, opportunities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(".cache/mechfight-kit"))
    parser.add_argument("--bot", type=Path, default=Path("bot.py"))
    parser.add_argument("--seed", type=int, default=1001)
    parser.add_argument("--count", type=int, default=32)
    args = parser.parse_args()
    with gzip.open(args.kit / "check/stream.jsonl.gz") as stream:
        hello, *rest = map(json.loads, stream)
    frames = [f for f in rest if f["type"] == "obs"]
    hello["map"]["dir"] = str(args.kit / "arena")
    arena = Arena(hello["map"]["dir"])
    bot_type = load_bot(args.bot, hello["map"]["dir"])
    hits, total = recorded_motion(bot_type, hello, arena, frames)
    print(f"Recorded-motion aim overlaps: {hits}/{total}", flush=True)
    captures = sum(movement_drill(bot_type, hello, arena, frames[0], seed)
                   for seed in range(args.seed, args.seed + args.count))
    print(f"Uncontested supply-drop captures in 28 s: {captures}/{args.count} (seed {args.seed} onward)")
    shelter = sum(movement_drill(bot_type, hello, arena, frames[0], seed, cover=True)
                  for seed in range(args.seed, args.seed + args.count))
    print(f"Mean time behind campus cover against one stationary observer: {shelter / args.count:.2f}/28 s")


if __name__ == "__main__":
    main()
