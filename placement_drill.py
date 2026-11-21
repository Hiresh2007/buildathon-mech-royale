"""Compare full-circle survival in a seeded approximation of the 15-member practice squad."""

import argparse
import collections
import copy
import gzip
import json
import math
import random
import statistics
from pathlib import Path

from benchmark import load_bot
from bot import Arena
from reward_drill import position, walk


# Mean HP change per visible actor-pair second from the organizer's public
# mechanics-v2-16 replay. The practice squad has a different engagement rule.
def proximity_rate(distance):
    for reach, hp in ((30, 135.5), (60, 50.9), (100, 21.9), (160, 8.0), (210, 2.8)):
        if distance <= reach:
            return hp
    return 0


def xy(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def circles(config, rng):
    center, radius, now = config["start_center"], config["start_radius"], 0
    phases = []
    for row in config["phases"]:
        angle = rng.random() * math.tau
        offset = math.sqrt(rng.random()) * (radius - row["radius"]) * 0.91
        target = [center[0] + offset * math.cos(angle), center[1] + offset * math.sin(angle)]
        start = now + row["hold_s"]
        now = start + row["shrink_s"]
        phases.append((now, start, center, radius, target, row["radius"], row["dps"]))
        center, radius = target, row["radius"]
    return phases


def world_zone(phases, now):
    end, start, center, radius, target, small, dps = next(
        (p for p in phases if now <= p[0]), phases[-1]
    )
    f = min(1, max(0, (now - start) / (end - start)))
    return dict(
        center=[a + f * (b - a) for a, b in zip(center, target)],
        radius=radius + f * (small - radius),
        next_center=target,
        next_radius=small,
        shrink_start=start,
        shrink_end=end,
        dps=dps,
    )


def house_walk(arena, actor, goal, now, step):
    pos = actor["pos"]
    if xy(pos, goal) < 2:
        return
    # A house member follows the official walkable grid. Limit route work the
    # same way for all seeds and both policies.
    if now >= actor["plan_at"] or xy(goal, actor["goal"]) > 32:
        actor["route"] = arena.route(pos, goal)
        actor["plan_at"] = now + 4
        actor["goal"] = goal
    while actor["route"] and xy(pos, actor["route"][0]) < 1:
        actor["route"].pop(0)
    if not actor["route"]:
        return
    dest = actor["route"][0]
    distance = xy(pos, dest)
    frac = min(1, step / max(distance, 0.01))
    pos[0] += (dest[0] - pos[0]) * frac
    pos[1] += (dest[1] - pos[1]) * frac
    node = arena.nearest_cell(pos)
    if node:
        pos[2] = arena.ground[node]


def spawn_locations(arena, cfg, rng):
    original = cfg["zone"]["start_center"]
    spawnable = [
        cell
        for cell in arena.ground
        if xy(position(arena, cell), original)
        < cfg["zone"]["start_radius"] * cfg["match"]["spawn_zone_fraction"]
    ]
    locations = []
    rng.shuffle(spawnable)
    for cell in spawnable:
        pos = position(arena, cell)
        if all(xy(pos, p) >= cfg["match"]["spawn_min_separation"] for p in locations):
            locations.append(pos)
            if len(locations) == cfg["match"]["mechs"]:
                break
    if len(locations) != cfg["match"]["mechs"]:
        raise ValueError("could not place the practice squad")
    return locations, spawnable


def supply_drops(arena, phases, drop_rules, rng):
    drops = []
    for i, when in enumerate(drop_rules["times"]):
        zone = world_zone(phases, when)
        choices = [
            c
            for c in arena.ground
            if xy(position(arena, c), zone["next_center"]) < zone["next_radius"] * 0.86
        ]
        if choices:
            drops.append(
                dict(
                    id=20000 + i,
                    pos=position(arena, rng.choice(choices)),
                    start=when,
                    lands=when + drop_rules["fall_s"],
                    radius=drop_rules["radius"],
                    capture_s=drop_rules["capture_s"],
                    progress=0.0,
                    holder=None,
                )
            )
    return drops


def apply_upgrade(me, item, cube_rules):
    model_bonus = 1.0
    for effect in item["effects"]:
        path = effect["path"].split(".")
        family, key = path[-2:]
        if family == "mech" and key in me["stats"]:
            old = me["stats"][key]
            me["stats"][key] = old * effect.get("mul", 1) + effect.get("add", 0)
            if key == "hp":
                added = (me["stats"]["hp"] - old) * (
                    1 + min(me["cubes"], cube_rules["stat_cap"]) * cube_rules["hp_per_cube"]
                )
                me["hp"] += added
                me["max_hp"] += added
            if key == "energy":
                me["energy"] += me["stats"][key] - old
                me["max_energy"] = me["stats"][key]
        elif family == "gun" and key == "damage":
            model_bonus *= effect.get("mul", 1.0)
        elif family == "gun" and key == "cooldown":
            model_bonus /= effect.get("mul", 1.0)
    return model_bonus


def trial(bot_class, hello, template, arena, seed, pressure, decision_step=0.25, burst=False):
    rng = random.Random(seed)
    cfg = hello["config"]
    me_rules, drop_rules, cube_rules = cfg["mech"], cfg["drops"], cfg["cubes"]
    phases = circles(cfg["zone"], rng)
    locations, spawnable = spawn_locations(arena, cfg, rng)
    slot = seed % cfg["match"]["mechs"]
    bot = bot_class(dict(hello, slot=slot))
    obs = copy.deepcopy(template)
    me = obs["self"]
    me.update(
        id=slot,
        pos=locations[0],
        vel=[0.0, 0.0, 0.0],
        hp=me_rules["hp"],
        max_hp=me_rules["hp"],
        energy=100.0,
        max_energy=100.0,
        grounded=True,
        cubes=0,
    )
    for field in (
        "mechs",
        "crates",
        "pickups",
        "cubes",
        "drops",
        "events",
        "sounds",
        "projectiles",
        "beams",
    ):
        obs[field] = []
    obs["offer"] = None
    houses = []
    for index, pos in enumerate(locations[1:], 1):
        houses.append(
            dict(
                id=(slot + index) % cfg["match"]["mechs"],
                pos=pos,
                hp=me_rules["hp"],
                strength=rng.uniform(0.65, 1.35),
                pace=rng.uniform(0.70, 1.0),
                delay=rng.uniform(6, 65),
                last_seen=-999.0,
                damaged=-999.0,
                plan_at=0.0,
                goal=pos[:2],
                route=[],
                ring_angle=rng.random() * math.tau,
            )
        )
    houses.sort(key=lambda actor: actor["strength"])
    upgrades = {item["id"]: item for item in cfg["upgrades"]}
    upgrade_rng = random.Random(seed + 2831)
    upgrade_counts = collections.Counter()
    thresholds = list(cube_rules["upgrade_thresholds"])
    model_bonus = 1.0
    drops = supply_drops(arena, phases, drop_rules, rng)
    # A fixed neutral pickup layout gives both controllers the same collectible opportunities.
    cubes = [dict(id=5000 + i, pos=position(arena, rng.choice(spawnable))) for i in range(48)]
    me["weapons"] = [copy.deepcopy(template["self"]["weapons"][0]), None]
    dt = decision_step
    physics_steps = max(1, round(dt * cfg["match"]["tick_hz"]))
    house_decisions = max(1, round(0.5 / dt))
    squad_decisions = max(1, round(1.0 / dt))
    last_spent = last_damage = -999.0
    winner = False
    damage_from_zone = 0.0
    next_tick = 0
    contact_rng = random.Random(seed + 61099)
    for tick in range(round(cfg["match"]["duration_s"] / dt)):
        now = tick * dt
        zone = world_zone(phases, now)
        pos = me["pos"]
        living = [a for a in houses if a["hp"] > 0]
        if not living:
            winner = True
            break
        hunters = (
            min(len(living), 1 + (len(living) < 11) + (len(living) < 7) * 2)
            if now < phases[3][1]
            else len(living)
        )
        if tick % squad_decisions == 0:
            active = {a["id"] for a in living[:hunters]}
        obs.update(t=now, tick=next_tick, alive=len(living) + 1, zone=zone)
        next_tick += physics_steps
        me["in_zone"] = xy(pos, zone["center"]) <= zone["radius"]
        if not me["in_zone"]:
            me["hp"] -= zone["dps"] * dt
            damage_from_zone += zone["dps"] * dt
            last_damage = now
        obs["drops"] = []
        for d in drops:
            if d["start"] <= now:
                d["lands_in"] = max(0, d["lands"] - now)
                obs["drops"].append(d)
        visible = []
        incoming = 0.0
        contacts = []
        for a in living:
            rival = a["pos"]
            dist = xy(pos, rival)
            if xy(rival, zone["center"]) > zone["radius"]:
                a["hp"] -= zone["dps"] * dt
                a["damaged"] = now
            elif now - a["damaged"] >= me_rules["regen_delay"]:
                a["hp"] = min(me_rules["hp"], a["hp"] + me_rules["regen_per_s"] * dt)
            if a["hp"] <= 0:
                continue
            can_see = dist < 205 and arena.clear_view(
                [pos[0], pos[1], pos[2] + 7], [rival[0], rival[1], rival[2] + 7]
            )
            if can_see and (
                dist < cfg["vision"]["near_range"]
                or abs(
                    math.remainder(
                        math.atan2(rival[1] - pos[1], rival[0] - pos[0]) - me["aim"][0], math.tau
                    )
                )
                < math.radians(60)
            ):
                a["last_seen"] = now
            if now - a["last_seen"] <= cfg["vision"]["memory_s"]:
                visible.append(
                    dict(
                        id=a["id"],
                        kind="mech",
                        pos=rival[:],
                        vel=[0, 0, 0],
                        hp=max(0, a["hp"]),
                        cubes=0,
                    )
                )
            if a["id"] in active:
                if can_see:
                    contacts.append((dist, a))
                    incoming += proximity_rate(dist) * a["strength"] * pressure
                goal = pos[:2] if dist > 30 else rival[:2]
            else:
                angle = a["ring_angle"]
                r = zone["next_radius"] * 0.65
                goal = [
                    zone["next_center"][0] + r * math.cos(angle),
                    zone["next_center"][1] + r * math.sin(angle),
                ]
                if (
                    xy(rival, zone["next_center"]) < zone["next_radius"] - 5
                    or now < zone["shrink_start"] + a["delay"]
                ):
                    goal = rival[:2]
            if tick % house_decisions == 0:
                house_walk(
                    arena, a, goal, now, me_rules["walk_speed"] * a["pace"] * dt * house_decisions
                )
        obs["mechs"] = visible
        obs["cubes"] = [c for c in cubes if xy(c["pos"], pos) < cfg["vision"]["near_range"]]
        if thresholds and me["cubes"] >= thresholds[0]:
            threshold = thresholds.pop(0)
            options = [
                item
                for item in upgrades.values()
                if upgrade_counts[item["id"]] < item["max"]
                and (
                    not item.get("requires")
                    or item["requires"] in {w["kind"] for w in me["weapons"] if w}
                )
            ]
            chosen = upgrade_rng.sample(options, min(3, len(options)))
            obs["offer"] = {"id": threshold, "expires": now + 5, "choices": chosen}
        else:
            obs["offer"] = None
        action = bot.act(obs)
        if obs["offer"]:
            item = obs["offer"]["choices"][action.get("pick", 0)]
            upgrade_counts[item["id"]] += 1
            model_bonus *= apply_upgrade(me, item, cube_rules)
        if burst:
            # Convert the same mean loss to discrete HP events, using common
            # random numbers for every policy in a matched seed.
            units = incoming * dt / 45
            whole = int(units)
            damage = (whole + (contact_rng.random() < units - whole)) * 45
            if damage:
                last_damage = now
        else:
            damage = incoming * dt
            if incoming > 5:
                last_damage = now
        me["hp"] -= damage * (1 - me["stats"]["armor"])
        if contacts:
            # Fixed reciprocal contact attrition for the unchanged contest action
            # code. No aiming, projectiles or equipment simulation is attempted.
            dist, a = min(contacts, key=lambda entry: entry[0])
            if any(action.get("fire", ())):
                a["hp"] -= (
                    proximity_rate(dist)
                    * 1.28
                    * dt
                    * (1 + 0.04 * min(10, me["cubes"]))
                    * model_bonus
                )
                a["damaged"] = now
                if a["hp"] <= 0:
                    for i in range(cube_rules["death_drop_extra"]):
                        cubes.append(dict(id=35000 + a["id"] * 4 + i, pos=a["pos"][:]))
                if dist < 160:
                    last_damage = now
        if me["hp"] <= 0:
            break
        if now - last_damage >= me["stats"]["regen_delay"] and me["in_zone"]:
            me["hp"] = min(me["max_hp"], me["hp"] + me["stats"]["regen_per_s"] * dt)
        if "aim" in action:
            yaw, pitch = me["aim"]
            to, up = action["aim"]
            cap = me_rules["turn_rate"] * dt
            me["aim"] = [yaw + max(-cap, min(cap, math.remainder(to - yaw, math.tau))), up]
        movement = dict(me["stats"])
        if action.get("boost") and me["energy"] >= movement["boost_drain"] * dt:
            movement["walk_speed"] = movement["boost_speed"]
            me["energy"] -= movement["boost_drain"] * dt
            last_spent = now
        elif now - last_spent >= movement["energy_regen_delay"]:
            me["energy"] = min(me["max_energy"], me["energy"] + movement["energy_regen"] * dt)
        for _ in range(physics_steps):
            walk(arena, me, action, movement, dt / physics_steps)
        for d in obs["drops"]:
            if (
                d["lands_in"] == 0
                and xy(me["pos"], d["pos"]) < d["radius"]
                and not any(xy(a["pos"], d["pos"]) < d["radius"] for a in living)
            ):
                d["progress"] += dt
                d["holder"] = slot
                if d["progress"] >= d["capture_s"]:
                    me["hp"] = me["max_hp"]
                    me["energy"] = me["max_energy"]
                    for j in range(drop_rules["cubes"]):
                        cubes.append(dict(id=50000 + d["id"] * 4 + j, pos=d["pos"]))
                    drops.remove(d)
            else:
                d["progress"] = 0.0
                d["holder"] = None
        new_cubes = [
            c
            for c in cubes
            if xy(me["pos"], c["pos"]) > cube_rules["pickup_radius"]
            or abs(me["pos"][2] - c["pos"][2]) > 4
        ]
        gain = len(cubes) - len(new_cubes)
        cubes = new_cubes
        credit = min(cube_rules["stat_cap"], gain + me["cubes"]) - min(
            cube_rules["stat_cap"], me["cubes"]
        )
        me["cubes"] += gain
        bonus = credit * me["stats"]["hp"] * cube_rules["hp_per_cube"]
        me["max_hp"] += bonus
        me["hp"] += bonus
        growth = 1.0 + me["cubes"] * cube_rules["size_per_cube"]
        for key in ("height", "radius", "eye_height", "muzzle_height"):
            me["stats"][key] = me_rules[key] * growth
    points = 15 if winner else sum(a["hp"] <= 0 for a in houses)
    if not winner and me["hp"] > 0:
        points += sum(0 < actor["hp"] < me["hp"] for actor in houses)
    return points, now, damage_from_zone, me["cubes"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(".cache/mechfight-kit"))
    parser.add_argument("--bots", type=Path, nargs="+", default=[Path("bot.py")])
    parser.add_argument("--seed", type=int, default=97001)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--pressure", type=float, default=1.0)
    parser.add_argument("--decision-step", type=float, choices=(0.1, 0.25), default=0.25)
    parser.add_argument(
        "--burst", action="store_true", help="apply equal-mean damage in 45-HP events"
    )
    args = parser.parse_args()
    with gzip.open(args.kit / "check/stream.jsonl.gz") as inp:
        hello, template = json.loads(next(inp)), json.loads(next(inp))
    directory = str((args.kit / "arena").resolve())
    hello["map"]["dir"] = directory
    arena = Arena(directory)
    arrays = []
    for path in args.bots:
        cls = load_bot(path, directory)
        rows = [
            trial(cls, hello, template, arena, s, args.pressure, args.decision_step, args.burst)
            for s in range(args.seed, args.seed + args.count)
        ]
        arrays.append(rows)
        print(
            path.name,
            "matches",
            len(rows),
            "points / seconds / zone HP lost / cubes",
            [round(statistics.mean(column), 2) for column in zip(*rows)],
            flush=True,
        )
    if len(arrays) == 2:
        print(
            "paired points",
            collections.Counter((b[0] > a[0]) - (b[0] < a[0]) for a, b in zip(*arrays)),
        )


if __name__ == "__main__":
    main()
