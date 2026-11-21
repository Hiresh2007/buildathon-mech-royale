"""Mech Royale placement bot for the mechfight/1 arena."""

import json
import heapq
import math
import sys
from array import array
from collections import defaultdict
from pathlib import Path

import mechfight


def inside(x, y, ring):
    """Even–odd test for the arena's flat polygon coordinate arrays."""
    hit = False
    ax, ay = ring[-2:]
    for i in range(0, len(ring), 2):
        bx, by = ring[i:i + 2]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
        ax, ay = bx, by
    return hit


class Arena:
    step = 8

    def __init__(self, directory):
        base = Path(directory) / "v2"
        world = json.loads((base / "world.json").read_bytes())
        self.bounds = world["bounds"]
        self.cells = defaultdict(list)
        for prism in world["prisms"]:
            xs, ys = prism["ring"][::2], prism["ring"][1::2]
            for i in range(math.floor(min(xs) / 24), math.floor(max(xs) / 24) + 1):
                for j in range(math.floor(min(ys) / 24), math.floor(max(ys) / 24) + 1):
                    self.cells[i, j].append(prism)
        terrain = world["terrain"]
        heights = array("h")
        heights.frombytes((base / terrain["file"]).read_bytes())
        if sys.byteorder != "little":
            heights.byteswap()
        self.terrain = terrain
        self.heights = heights
        self.ground = {}
        for i in range(math.ceil(self.bounds["minX"] / self.step), math.ceil(self.bounds["maxX"] / self.step)):
            for j in range(math.ceil(self.bounds["minY"] / self.step), math.ceil(self.bounds["maxY"] / self.step)):
                x, y = i * self.step, j * self.step
                col = round((x - terrain["minX"]) / terrain["step"])
                row = round((y - terrain["minY"]) / terrain["step"])
                z = heights[row * terrain["nx"] + col] * terrain["scale"]
                if not any(self.blocked(x + dx, y + dy, z, 9) for dx, dy in
                           ((0, 0), (2.5, 0), (-2.5, 0), (0, 2.5), (0, -2.5))):
                    self.ground[i, j] = z
        self.neighbors = {}
        midpoints = {}
        for (i, j), height in self.ground.items():
            edges = []
            for di, dj in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                node = i + di, j + dj
                if node not in self.ground:
                    continue
                if di and dj and ((i + di, j) not in self.ground or (i, j + dj) not in self.ground):
                    continue
                middle = (2 * i + di, 2 * j + dj)
                if middle not in midpoints:
                    x, y = (a * self.step / 2 for a in middle)
                    z = (height + self.ground[node]) / 2
                    midpoints[middle] = not any(self.blocked(x + dx, y + dy, z, 9) for dx, dy in
                                               ((0, 0), (2.5, 0), (-2.5, 0), (0, 2.5), (0, -2.5)))
                if not midpoints[middle]:
                    continue
                length = math.hypot(di, dj)
                slope = abs(self.ground[node] - height) / (length * self.step)
                if slope < 1.1:
                    edges.append((node, length * (1 + 0.2 * slope)))
            self.neighbors[i, j] = edges

    def blocked(self, x, y, feet, height):
        b = self.bounds
        if not (b["minX"] + 3 < x < b["maxX"] - 3 and b["minY"] + 3 < y < b["maxY"] - 3):
            return True
        for p in self.cells.get((math.floor(x / 24), math.floor(y / 24)), ()):
            if p["base"] >= feet + height or p["top"] <= feet + 1.2:
                continue
            if inside(x, y, p["ring"]) and not any(inside(x, y, h) for h in p["holes"]):
                return True
        return False

    def nearest_cell(self, point):
        i, j = (round(v / self.step) for v in point[:2])
        if (i, j) in self.ground:
            return i, j
        candidates = ((i + dx, j + dy) for dx in range(-4, 5) for dy in range(-4, 5))
        return min((cell for cell in candidates if cell in self.ground),
                   key=lambda cell: math.hypot(cell[0] * self.step - point[0], cell[1] * self.step - point[1]),
                   default=None)

    def clear_view(self, start, end):
        """Check static arena cover for actors still present in the vision memory."""
        steps = math.ceil(math.dist(start, end) / 4)
        terrain = self.terrain
        for i in range(1, steps):
            f = i / steps
            x = start[0] + f * (end[0] - start[0])
            y = start[1] + f * (end[1] - start[1])
            z = start[2] + f * (end[2] - start[2])
            col = min(terrain["nx"] - 1, max(0, round((x - terrain["minX"]) / terrain["step"])))
            row = min(terrain["ny"] - 1, max(0, round((y - terrain["minY"]) / terrain["step"])))
            if self.heights[row * terrain["nx"] + col] * terrain["scale"] > z:
                return False
            if self.blocked(x, y, z - 1.2, 1.2):
                return False
        return True

    def route(self, start, end):
        source, target = self.nearest_cell(start), self.nearest_cell(end)
        if source is None or target is None or source == target:
            return []
        costs = {source: 0}
        parents = {}
        pending = [(math.dist(source, target), 0, source)]
        # A distant or isolated destination must still fit in one game tick.
        closest = source
        for _ in range(1800):
            if not pending:
                break
            _, cost, cell = heapq.heappop(pending)
            if cost > costs[cell]:
                continue
            if math.dist(cell, target) < math.dist(closest, target):
                closest = cell
            if cell == target:
                break
            for neighbor, length in self.neighbors[cell]:
                new_cost = cost + length
                if new_cost < costs.get(neighbor, math.inf):
                    costs[neighbor], parents[neighbor] = new_cost, cell
                    heapq.heappush(pending, (new_cost + math.dist(neighbor, target), new_cost, neighbor))
        waypoints = []
        while closest != source:
            waypoints.append([closest[0] * self.step, closest[1] * self.step])
            closest = parents[closest]
        return waypoints[::-1]


def xy_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Bot:
    name = "Outlast"

    def __init__(self, hello):
        self.arena = Arena(hello["map"]["dir"])
        self.config = hello["config"]
        self.side = 1 if hello["slot"] % 2 else -1
        self.heading = None
        self.last_position = None
        self.last_check = 0
        self.climb_until = 0
        self.waypoints = []
        self.route_goal = None
        self.replan_at = 0
        self.supplies = {}
        self.focus = None
        self.cover_goal = None
        self.cover_check_at = 0
        self.cover_until = 0
        self.listen_yaw = None
        self.listen_until = 0
        self.last_npc_damage = -math.inf
        self.reward_sprint = False
        self.recent_attackers = {}
        self.duel_target = None
        self.duel_until = -math.inf
        self.aim_priority = None
        self.previous_rivals = {}
        self.kill_reward = None

    def shelter(self, obs, enemy, distance):
        """Look for nearby walkable campus cover while waiting for HP regeneration."""
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        if me["hp"] >= 0.65 * me["max_hp"]:
            self.cover_goal = None
            return None
        pos, height = me["pos"], me["stats"]["height"]
        if enemy is None:
            return self.cover_goal if now < self.cover_until else None
        if distance > 160 or enemy.get("hp", math.inf) < 0.24 * me["max_hp"]:
            return None
        if now < self.cover_check_at:
            return self.cover_goal
        self.cover_check_at = now + 0.65
        self.cover_goal = None
        source = enemy["pos"].copy()
        source[2] += self.config["mech"]["muzzle_height"] * (1 + enemy.get("cubes", 0) * self.config["cubes"]["size_per_cube"])
        facing = math.atan2(pos[1] - source[1], pos[0] - source[0])
        for radius in (0, 15, 30, 48, 68):
            # Prefer escape cells farther from this hunter and nearer to the
            # safe side of the ring. Stop on the first usable distance band.
            best = None
            for index in range(1 if radius == 0 else 10):
                angle = facing + index * math.tau / 10
                x, y = pos[0] + radius * math.cos(angle), pos[1] + radius * math.sin(angle)
                cell = (round(x / self.arena.step), round(y / self.arena.step))
                if cell not in self.arena.ground:
                    continue
                if radius:
                    x, y = cell[0] * self.arena.step, cell[1] * self.arena.step
                if xy_distance((x, y), zone["center"]) >= zone["radius"] - 3:
                    continue
                separation = xy_distance((x, y), source)
                if separation < min(distance - 2, 25):
                    continue
                head = (x, y, (self.arena.ground[cell] if radius else pos[2]) + height * 0.85)
                if self.arena.clear_view(source, head):
                    continue
                cost = xy_distance(pos, head) - 0.4 * separation + 0.08 * xy_distance(head, zone["next_center"])
                if best is None or cost < best[0]:
                    best = (cost, [x, y])
            if best:
                self.cover_goal = best[1]
                self.cover_until = now + me["stats"]["regen_delay"] + 2
                break
        return self.cover_goal

    def secondary_upgrades(self, weapons, pickups, enemy_distance):
        primary, secondary = weapons
        if not primary or primary["kind"] != "gun" or not secondary:
            return []
        kind = secondary["kind"]
        if kind == "mortar":
            return [p for p in pickups if p["kind"] in ("lightning", "laser")]
        if kind == "lightning" and enemy_distance >= secondary["stats"]["range"] + 12:
            return [p for p in pickups if p["kind"] == "laser"]
        return []

    def upgrade_waypoint(self, pos, goal, zone, upgrades):
        direct = xy_distance(pos, goal)
        options = []
        for item in upgrades:
            point = item["pos"]
            distance = xy_distance(pos, point)
            extra = distance + xy_distance(point, goal) - direct
            if (distance < 68 and extra < 33 and abs(pos[2] - point[2]) < 5
                    and xy_distance(point, zone["center"]) < zone["radius"] - 4):
                cost = extra + 0.12 * distance - (5 if item["kind"] == "laser" else 0)
                options.append((cost, point))
        return min(options, key=lambda option: option[0])[1] if options else None

    def loot_goal(self, obs, enemy_distance):
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        pos = me["pos"]
        free_slot = None in me["weapons"]
        # Crates and cubes disappear from obs as soon as the torso turns away.
        # Remember them only until we have had time to get there and inspect them.
        seen = set()
        for name in ("crates", "pickups", "cubes"):
            for item in obs[name]:
                seen.add(item["id"])
                if name != "pickups" or (free_slot and item["kind"] != "gun"):
                    self.supplies[item["id"]] = (name, item, now)
        choices = []
        for key, (name, item, last_seen) in list(self.supplies.items()):
            distance = xy_distance(pos, item["pos"])
            if (now - last_seen > 12 or (distance < 9 and key not in seen)
                    or (name == "pickups" and not free_slot)):
                del self.supplies[key]
                continue
            if (distance > 86 or abs(item["pos"][2] - pos[2]) > 5
                    or xy_distance(item["pos"], zone["center"]) > zone["radius"] - 3):
                continue
            # A crate has to be opened. Favor loose cubes and useful second slots.
            penalty = {"cubes": 0, "pickups": 3, "crates": 24}[name]
            if name == "pickups" and item["kind"] == "laser":
                penalty -= 9
            if name == "crates" and distance < 8:
                continue
            choices.append((distance + penalty, item["pos"], False))
        if ((not free_slot or not choices) and me["cubes"] < 3
                and me["hp"] > 0.80 * me["max_hp"] and enemy_distance > 95):
            for drone in obs["mechs"]:
                if drone["kind"] != "npc" or drone["id"] != self.focus:
                    continue
                point = drone["pos"]
                distance = xy_distance(pos, point)
                if (distance <= 80 and abs(pos[2] - point[2]) <= 4
                        and xy_distance(point, zone["center"]) <= zone["radius"] - 10):
                    # A drone already under fire drops two cubes at its feet.
                    choices.append((distance - 7, point, False))
        for drop in obs["drops"]:
            distance = xy_distance(pos, drop["pos"])
            eta = distance / me["stats"]["walk_speed"]
            # Drops are announced globally 25 seconds before landing. The previous
            # fixed distance cutoff discarded announcements reachable within that window.
            if (drop["holder"] not in (None, me["id"]) or eta > max(12, drop["lands_in"] + 9)
                    or drop["lands_in"] > eta + 9 or enemy_distance < 35
                    or xy_distance(drop["pos"], zone["center"]) >= zone["radius"] - 3):
                continue
            reward = 105 if me["hp"] < 0.85 * me["max_hp"] else 70
            hold = distance < drop["radius"] * 0.65
            choices.append((distance + max(0, drop["lands_in"] - eta) * 3 - reward,
                            drop["pos"], hold))
        return min(choices, key=lambda entry: entry[0]) if choices else None

    def recovery_goal(self, obs):
        """Collect a near-term health reward using the arena's actual capture clocks."""
        me, zone = obs["self"], obs["zone"]
        pos = me["pos"]
        for drop in obs["drops"]:
            if (drop["holder"] == me["id"] and drop["progress"] > 0
                    and xy_distance(pos, drop["pos"]) < drop["radius"] - 0.6
                    and (drop["capture_s"] - drop["progress"] <= 2.5 or me["hp"] < 0.75 * me["max_hp"])):
                return drop["pos"], True

        cfg = self.config["cubes"]
        if me["cubes"] >= cfg["stat_cap"] or not obs["cubes"]:
            return None
        reach = cfg["pickup_radius"]
        distance_budget = reach + me["stats"]["walk_speed"] * (1.7 if me["cubes"] == 0 or me["hp"] < 0.8 * me["max_hp"] else 0.9)
        nearby = [(xy_distance(pos, c["pos"]), c) for c in obs["cubes"]
                  if abs(c["pos"][2] - pos[2]) <= 4
                  and xy_distance(c["pos"], zone["center"]) < zone["radius"] - reach]
        nearby = [(d, c) for d, c in nearby if d <= distance_budget]
        if not nearby:
            return None
        # A pickup is automatic within the horizontal ring. Several cubes from
        # the same reward can therefore be collected in a single visit.
        def value(entry):
            distance, cube = entry
            count = sum(xy_distance(cube["pos"], other["pos"]) <= reach
                        and abs(cube["pos"][2] - other["pos"][2]) <= 2 for _, other in nearby)
            credit = min(count, cfg["stat_cap"] - me["cubes"])
            return max(0, distance - reach) / max(1, credit), distance, cube["id"]
        # A mass pickup can make many items coincide. Score the nearest candidates
        # against the full group without a quadratic pass on a busy server tick.
        candidates = sorted(nearby, key=lambda entry: (entry[0], entry[1]["id"]))[:24]
        _, cube = min(candidates, key=value)
        return cube["pos"], False

    def confirmed_reward(self, obs, opponents, available):
        """Remember a defeated opponent's cube pile while it is safe to collect."""
        me, now = obs["self"], obs["t"]
        pos = me["pos"]
        for event in obs["events"]:
            if event["type"] != "kill":
                continue
            last_seen = self.previous_rivals.get(event["target"])
            if last_seen is None:
                continue
            seen_at, point, cubes = last_seen
            distance = xy_distance(pos, point)
            if now - seen_at < 2.5 and 75 < distance < 158 and abs(pos[2] - point[2]) < 5:
                travel_window = min(15, 3 + distance / 10)
                self.kill_reward = (point, now + travel_window, cubes + 2)

        for actor in opponents:
            self.previous_rivals[actor["id"]] = (now, actor["pos"][:], actor.get("cubes", 0))
        if self.kill_reward is None:
            return None

        point, expires, cubes = self.kill_reward
        distance = xy_distance(pos, point)
        if now > expires or me["cubes"] >= self.config["cubes"]["stat_cap"] or distance < 11:
            self.kill_reward = None
            return None
        if (not available or me["hp"] < 0.52 * me["max_hp"]
                or xy_distance(point, obs["zone"]["center"]) > obs["zone"]["radius"] - 10
                or abs(pos[2] - point[2]) > 5):
            return None
        for actor in opponents:
            if (xy_distance(pos, actor["pos"]) < 78
                    or xy_distance(point, actor["pos"]) < min(82, distance + 8)):
                return None
        if any(xy_distance(pos, cube["pos"]) < 17 for cube in obs["cubes"]):
            return None

        cluster = [cube for cube in obs["cubes"] if xy_distance(cube["pos"], point) < 10]
        if not cluster and distance < 36:
            self.kill_reward = None
            return None
        if cubes < 3 and distance > 122:
            return None
        if cluster:
            return min(cluster, key=lambda cube: xy_distance(pos, cube["pos"]))["pos"]
        return point

    def duel_goal(self, obs, opponents, available):
        """Hold a usable distance from one isolated, inattentive arena avatar."""
        me, now = obs["self"], obs["t"]
        self.aim_priority = None
        for event in obs["events"]:
            source = event.get("by")
            if event["type"] == "damaged" and source is not None:
                self.recent_attackers[source] = now

        if not available or obs["alive"] <= 5 or now >= 185 or me["hp"] <= 0.67 * me["max_hp"]:
            return None

        pos = me["pos"]
        candidates = []
        for rival in opponents:
            point, actor_id = rival["pos"], rival["id"]
            distance, aim = xy_distance(pos, point), rival.get("aim")
            if aim is None or not 16 < distance < 150:
                continue

            direction = math.atan2(pos[1] - point[1], pos[0] - point[0])
            rear = abs(math.remainder(direction - aim[0], math.tau)) > 1.77
            enemy_hp = rival.get("hp", 1400)
            finishing = enemy_hp < 0.42 * me["hp"]
            same_duel = actor_id == self.duel_target and now < self.duel_until
            if not rear and not (same_duel and finishing):
                continue
            if not finishing and (me["hp"] <= 0.83 * me["max_hp"]
                                  or now - self.recent_attackers.get(actor_id, -99) < 2):
                continue

            others = [actor for actor in opponents if actor["id"] != actor_id]
            if any(now - self.recent_attackers.get(actor["id"], -99) < 3.5
                   or xy_distance(pos, actor["pos"]) < 80
                   or xy_distance(point, actor["pos"]) < 55 for actor in others):
                continue
            origin = [pos[0], pos[1], pos[2] + me["stats"]["muzzle_height"]]
            height = self.config["mech"]["height"] * (1 + self.config["cubes"]["size_per_cube"] * rival.get("cubes", 0))
            center = [point[0], point[1], point[2] + 0.5 * height]
            if self.arena.clear_view(origin, center):
                cost = distance + 0.035 * enemy_hp - (18 if same_duel else 0)
                candidates.append((cost, rival, distance))

        if not candidates:
            return None
        _, rival, distance = min(candidates, key=lambda candidate: candidate[0])
        self.aim_priority = self.duel_target = rival["id"]
        self.duel_until = now + 2
        point = rival["pos"]
        stand_off = 32 if any(w and w["kind"] == "lightning" for w in me["weapons"]) else 56
        goal = [point[i] + (pos[i] - point[i]) / distance * stand_off for i in (0, 1)]
        return goal if xy_distance(goal, obs["zone"]["center"]) < obs["zone"]["radius"] - 6 else None

    def engage(self, obs, action):
        me, stats = obs["self"], obs["self"]["stats"]
        pos = me["pos"]
        config = self.config
        origin = (pos[0], pos[1], pos[2] + stats["muzzle_height"])
        options = []
        for actor in obs["mechs"] + obs["crates"]:
            kind = actor.get("kind", "crate")
            if kind != "mech" and self.cover_goal is not None and obs["t"] < self.cover_until:
                continue
            if kind == "mech":
                height = config["mech"]["height"] * (1 + config["cubes"]["size_per_cube"] * actor.get("cubes", 0))
            else:
                height = config["npc" if kind == "npc" else "crates"]["height"]
            x, y, z = actor["pos"]
            center = (x, y, z + height * 0.5)
            d = math.dist(origin, center)
            cost = d + 0.06 * actor.get("hp", 0) - (18 if self.focus == actor["id"] else 0)
            if kind == "mech" and actor["id"] == self.aim_priority:
                cost -= 65
            options.append((kind != "mech", cost, actor, center, d))
        for _, _, actor, center, distance in sorted(options, key=lambda o: o[:2]):
            if not self.arena.clear_view(origin, center):
                continue
            self.focus = actor["id"]
            break
        else:
            self.focus = None
            return
        weapons = me["weapons"]
        laser = next((w for w in weapons if w and w["kind"] == "laser"), None)
        gun = next((w for w in weapons if w and w["kind"] == "gun"), None)
        # While a laser is ready to release its hit is instantaneous. Otherwise
        # advance moving game actors by the gun's travel time from the muzzle.
        aim_at = center
        if gun and not (laser and laser.get("charge", 0) >= laser["stats"]["charge"] - 0.1):
            travel = max(0, distance - stats["radius"] - 0.5) / gun["stats"]["speed"]
            vx, vy, vz = actor.get("vel", (0, 0, 0))
            aim_at = (center[0] + vx * travel, center[1] + vy * travel, center[2] + vz * travel)
        yaw = math.atan2(aim_at[1] - pos[1], aim_at[0] - pos[0])
        pitch = math.atan2(aim_at[2] - origin[2], xy_distance(aim_at, pos))
        pitch = max(stats["min_pitch"], min(stats["max_pitch"], pitch))
        action["aim"] = [yaw, pitch]
        yaw_error = abs(math.remainder(yaw - me["aim"][0], 2 * math.pi))
        aligned = yaw_error < 0.10 and abs(pitch - me["aim"][1]) < 0.10
        trigger = []
        for weapon in weapons:
            fire = False
            if weapon:
                kind, ws = weapon["kind"], weapon["stats"]
                if kind == "lightning":
                    target_yaw = math.atan2(center[1] - pos[1], center[0] - pos[0])
                    fire = distance <= ws["range"] and abs(math.remainder(target_yaw - me["aim"][0], 2 * math.pi)) < math.radians(ws["cone_deg"])
                elif kind == "laser":
                    fire = distance <= ws["range"] and (not aligned or weapon.get("charge", 0) < ws["charge"] - 0.025)
                elif kind == "mortar":
                    fire = aligned and 16 < distance < 58
                else:
                    fire = aligned and distance <= ws["range"]
            trigger.append(fire)
        action["fire"] = trigger

    def waypoint(self, pos, goal, t):
        if xy_distance(pos, goal) < 18:
            return goal
        if self.route_goal is None or t >= self.replan_at or xy_distance(goal, self.route_goal) > 24:
            self.route_goal = goal
            self.replan_at = t + 2
            self.waypoints = self.arena.route(pos, goal)
        while self.waypoints and xy_distance(pos, self.waypoints[0]) < 3.5:
            self.waypoints.pop(0)
        return self.waypoints[0] if self.waypoints else goal

    def steer(self, position, goal, height, radius=2.5):
        dx, dy = goal[0] - position[0], goal[1] - position[1]
        if math.hypot(dx, dy) < 1.5:
            return [0, 0]
        target = math.atan2(dy, dx)
        best = None
        for turn in (0, 0.45, -0.45, 0.9, -0.9, 1.45, -1.45, 2.1, -2.1, math.pi):
            angle = target + self.side * turn
            vx, vy = math.cos(angle), math.sin(angle)
            cost = abs(turn)
            if self.heading is not None:
                cost += 0.4 * (1 - math.cos(self.heading - angle))
            for distance, weight in ((2, 12), (5, 7), (10, 3), (17, 1)):
                x, y = position[0] + vx * distance, position[1] + vy * distance
                if any(self.arena.blocked(x + dx, y + dy, position[2], height)
                       for dx, dy in ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius))):
                    cost += weight
            if best is None or cost < best[0]:
                best = (cost, angle, [vx, vy])
        self.heading = best[1]
        return best[2]

    def act(self, obs):
        me, zone, t = obs["self"], obs["zone"], obs["t"]
        pos, stats = me["pos"], me["stats"]
        center, radius = zone["next_center"], zone["next_radius"]
        ring_angle = math.atan2(pos[1] - center[1], pos[0] - center[0]) + 0.45 * self.side
        goal = [center[0] + math.cos(ring_angle) * radius * 0.67,
                center[1] + math.sin(ring_angle) * radius * 0.67]
        urgent = (not me["in_zone"] or
                  xy_distance(pos, center) - radius > max(0, zone["shrink_end"] - t - 3) * stats["walk_speed"] * 0.7)
        if urgent:
            goal = center
        opponents = [a for a in obs["mechs"] if a["kind"] == "mech"]
        enemy = min(opponents, key=lambda a: xy_distance(pos, a["pos"]), default=None)
        enemy_distance = xy_distance(pos, enemy["pos"]) if enemy else math.inf
        near_pickups = [p for p in obs["pickups"] if p["kind"] != "gun"]
        upgrades = self.secondary_upgrades(me["weapons"], near_pickups, enemy_distance)
        empty_slot = None in me["weapons"]
        eligible = near_pickups if empty_slot else upgrades
        reachable = [p for p in eligible if xy_distance(pos, p["pos"]) < self.config["loot"]["pickup_radius"]
                     and abs(pos[2] - p["pos"][2]) <= 4]
        take = min(reachable, key=lambda p: (not empty_slot and p["kind"] != "laser",
                                            xy_distance(pos, p["pos"])), default=None)
        supply = self.loot_goal(obs, enemy_distance)
        cover = None if urgent else self.shelter(obs, enemy, enemy_distance)
        recovery = None if urgent else self.recovery_goal(obs)
        holding = False
        approaching_reward = False
        if recovery is not None:
            goal, holding = recovery
            approaching_reward = True
        elif cover is not None:
            goal = cover
            holding = xy_distance(pos, cover) < 4
        elif not urgent and supply and enemy_distance > 65:
            goal, holding = supply[1:]
            approaching_reward = (any(cube["pos"] == goal for cube in obs["cubes"])
                                  or any(drop["pos"] == goal for drop in obs["drops"]))
        elif not urgent and enemy_distance < 100:
            # Legs move independently of the torso. Keep moving across a hunter's
            # view, opening more distance when several opponents arrive.
            turn = 0.70 if len(opponents) > 1 or me["hp"] < 0.45 * me["max_hp"] else 1.35
            a = math.atan2(pos[1] - enemy["pos"][1], pos[0] - enemy["pos"][0])
            escape = [pos[0] + 22 * math.cos(a + turn * self.side),
                      pos[1] + 22 * math.sin(a + turn * self.side)]
            if xy_distance(escape, zone["center"]) < zone["radius"] - 3:
                goal = escape

        if (upgrades and not urgent and not holding and cover is None
                and enemy_distance > 82 and me["hp"] > 0.58 * me["max_hp"]):
            waypoint = self.upgrade_waypoint(pos, goal, zone, upgrades)
            if waypoint is not None:
                goal = waypoint
                approaching_reward = True

        reward = self.confirmed_reward(obs, opponents, not urgent and not holding and cover is None)
        if reward is not None:
            goal = reward
            approaching_reward = True

        duel = self.duel_goal(obs, opponents, not urgent and not holding and cover is None)
        if duel is not None:
            goal = duel
            holding = xy_distance(pos, goal) < 3
            approaching_reward = False

        move = [0, 0] if holding else self.steer(pos, self.waypoint(pos, goal, t), stats["height"], stats["radius"])
        if t >= self.last_check + 1.5:
            if self.last_position and xy_distance(self.last_position, pos) < 2 and xy_distance(pos, goal) > 9:
                self.climb_until = t + 1.3
            self.last_position, self.last_check = pos, t
        climbing = not holding and t < self.climb_until and me["energy"] > 15
        # Use surplus rechargeable energy for collectible trips. Hysteresis
        # makes the regeneration delay apply once per burst, not once per tick.
        threshold = 0.53 if self.reward_sprint else 0.83
        self.reward_sprint = (approaching_reward and not holding and me["grounded"]
                              and xy_distance(pos, goal) > self.config["cubes"]["pickup_radius"] + 2.5
                              and me["energy"] > threshold * me["max_energy"])
        action = {"move": move, "boost": self.reward_sprint or climbing or ((urgent or enemy_distance < 60) and me["energy"] > 35),
                  "jump": climbing and me["grounded"]}
        if take:
            action["take"] = take["id"]
            if not empty_slot:
                action["drop"] = 1
        if obs["offer"]:
            preference = ("plating", "gun_damage", "gun_rate", "armor", "laser_damage", "nanites", "servos", "reactor")
            choices = obs["offer"]["choices"]
            action["pick"] = min(range(len(choices)), key=lambda i:
                                 preference.index(choices[i]["id"]) if choices[i]["id"] in preference else len(preference))

        # Damage dealt to a crate or NPC also restarts the five-second HP timer.
        # While alone and wounded, let passive repairs run to a usable HP level.
        if any(event["type"] == "damaged" and event.get("weapon") == "npc" for event in obs["events"]):
            self.last_npc_damage = t
        repairing = (me["in_zone"] and me["hp"] < 0.82 * me["max_hp"] and not opponents
                     and t - self.last_npc_damage > stats["regen_delay"])
        if not repairing:
            self.engage(obs, action)
        if "aim" not in action:
            bearing = next((e["bearing"] for e in obs["events"]
                            if e["type"] == "damaged" and e.get("bearing") is not None), None)
            if bearing is None:
                bearing = next((s["bearing"] for s in obs["sounds"]
                                if s["dist"] != "far" and s["kind"] in ("gun", "laser", "laser_charge", "lightning", "mortar")), None)
            if bearing is not None:
                self.listen_yaw, self.listen_until = bearing, t + 1
            scan = (self.heading or 0) + math.sin(t * 0.8) * 1.25
            action["aim"] = [self.listen_yaw if t < self.listen_until else scan, 0]
            action["reload"] = any(w and w["kind"] == "gun" and w["ammo"] < w["stats"]["mag"]
                                   for w in me["weapons"])
        return action


if __name__ == "__main__":
    mechfight.run(Bot)
