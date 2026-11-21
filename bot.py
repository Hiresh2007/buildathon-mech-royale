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
        for (i, j), height in self.ground.items():
            edges = []
            for di, dj in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                node = i + di, j + dj
                if node not in self.ground:
                    continue
                if di and dj and ((i + di, j) not in self.ground or (i, j + dj) not in self.ground):
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

    def waypoint(self, pos, goal, t):
        if xy_distance(pos, goal) < 18:
            return goal
        if self.route_goal is None or t >= self.replan_at or xy_distance(goal, self.route_goal) > 24:
            self.route_goal = goal
            self.replan_at = t + 2
            self.waypoints = self.arena.route(pos, goal)
        while self.waypoints and xy_distance(pos, self.waypoints[0]) < 6:
            self.waypoints.pop(0)
        return self.waypoints[0] if self.waypoints else goal

    def steer(self, position, goal, height):
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
            for distance, weight in ((5, 6), (10, 3), (18, 1)):
                if self.arena.blocked(position[0] + vx * distance, position[1] + vy * distance,
                                      position[2], height):
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
        take = None
        if None in me["weapons"]:
            reachable = [p for p in near_pickups if xy_distance(pos, p["pos"]) < self.config["loot"]["pickup_radius"]
                         and abs(pos[2] - p["pos"][2]) <= 4]
            take = min(reachable, key=lambda p: xy_distance(pos, p["pos"]), default=None)
        loot = list(obs["cubes"])
        if None in me["weapons"]:
            loot.extend(near_pickups)
        if me["hp"] < 0.85 * me["max_hp"]:
            loot.extend(d for d in obs["drops"] if d["lands_in"] <= 2)
        if not urgent and enemy_distance > 70:
            choices = [p for p in loot if xy_distance(p["pos"], zone["center"]) < zone["radius"] - 3
                       and xy_distance(p["pos"], pos) < 55 and abs(p["pos"][2] - pos[2]) < 12]
            if choices:
                goal = min(choices, key=lambda p: xy_distance(p["pos"], pos))["pos"]
        elif not urgent and enemy_distance < 70:
            # Sidestep around the circle and leave room to regenerate HP.
            a = math.atan2(pos[1] - enemy["pos"][1], pos[0] - enemy["pos"][0]) + 0.65 * self.side
            escape = [pos[0] + 25 * math.cos(a), pos[1] + 25 * math.sin(a)]
            if xy_distance(escape, zone["center"]) < zone["radius"] - 3:
                goal = escape

        move = self.steer(pos, self.waypoint(pos, goal, t), stats["height"])
        if t >= self.last_check + 1.5:
            if self.last_position and xy_distance(self.last_position, pos) < 2 and xy_distance(pos, goal) > 9:
                self.climb_until = t + 1.3
            self.last_position, self.last_check = pos, t
        climbing = t < self.climb_until and me["energy"] > 15
        action = {"move": move, "boost": climbing or ((urgent or enemy_distance < 60) and me["energy"] > 35),
                  "jump": climbing and me["grounded"]}
        if take:
            action["take"] = take["id"]
        if obs["offer"]:
            preference = ("nanites", "armor", "plating", "servos", "reactor", "gun_rate", "gun_damage")
            choices = obs["offer"]["choices"]
            action["pick"] = min(range(len(choices)), key=lambda i:
                                 preference.index(choices[i]["id"]) if choices[i]["id"] in preference else len(preference))

        target = enemy
        if target is None:
            targets = obs["crates"] + [a for a in obs["mechs"] if a["kind"] == "npc"]
            target = min(targets, key=lambda a: xy_distance(pos, a["pos"]), default=None)
        if target:
            tx, ty, tz = target["pos"]
            height = {"mech": 4.5 * (1 + 0.05 * target.get("cubes", 0)), "npc": 1.75}.get(target.get("kind"), 1.2)
            yaw = math.atan2(ty - pos[1], tx - pos[0])
            distance = xy_distance(pos, target["pos"])
            pitch = math.atan2(tz + height - pos[2] - stats["muzzle_height"], distance)
            pitch = max(stats["min_pitch"], min(stats["max_pitch"], pitch))
            action["aim"] = [yaw, pitch]
            aligned = math.cos(yaw - me["aim"][0]) > 0.994 and abs(pitch - me["aim"][1]) < 0.10
            action["fire"] = [bool(w and aligned and distance <= w["stats"].get("range", 85))
                              for w in me["weapons"]]
        else:
            action["aim"] = [(self.heading or 0) + math.sin(t * 0.8) * 1.25, 0]
            action["reload"] = any(w and w["kind"] == "gun" and w["ammo"] < w["stats"]["mag"]
                                   for w in me["weapons"])
        return action


if __name__ == "__main__":
    mechfight.run(Bot)
