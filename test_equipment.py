import unittest
from unittest.mock import Mock, patch

from bot import Bot


class SecondaryEquipmentTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0,
                            "config": {"mech": {"height": 9}, "cubes": {"size_per_cube": 0.05}}})
        self.gun = {"kind": "gun"}
        self.mortar = {"kind": "mortar"}
        self.lightning = {"kind": "lightning", "stats": {"range": 35}}
        self.laser = {"id": 10, "kind": "laser", "pos": [20, 0, 0]}
        self.arc = {"id": 20, "kind": "lightning", "pos": [15, 0, 0]}

    def test_routes_to_a_recently_seen_upgrade_until_it_expires(self):
        self.bot.config["cubes"].update(stat_cap=10, pickup_radius=3.5)
        self.bot.config["loot"] = {"pickup_radius": 4}
        self.bot.waypoint = lambda pos, goal, now: goal
        self.bot.steer = Mock(return_value=[1, 0])
        gun = {"kind": "gun", "ammo": 12, "stats": {"mag": 12}}
        me = {"id": 0, "pos": [0, 0, 0], "weapons": [gun, self.mortar], "cubes": 0,
              "in_zone": True, "hp": 100, "max_hp": 100, "grounded": True,
              "energy": 80, "max_energy": 100, "aim": [0, 0],
              "stats": {"walk_speed": 11.7, "radius": 2.5, "height": 9, "muzzle_height": 7}}
        obs = {"self": me, "t": 1, "alive": 12, "zone": {"center": [0, 0], "radius": 300,
               "next_center": [100, 0], "next_radius": 0, "shrink_end": 200},
               "pickups": [self.laser], "cubes": [], "crates": [], "drops": [], "mechs": [],
               "events": [], "sounds": [], "projectiles": [], "offer": None}
        first = self.bot.act(obs)
        self.assertEqual(self.bot.steer.call_args.args[1], self.laser["pos"])
        self.assertNotIn("take", first)

        obs.update(t=3, pickups=[])
        self.assertNotIn("take", self.bot.act(obs))
        self.assertEqual(self.bot.steer.call_args.args[1], self.laser["pos"])

        arc = dict(self.arc, pos=[25, 0, 0])
        obs.update(t=4, pickups=[arc])
        self.bot.act(obs)
        self.assertEqual(self.bot.steer.call_args.args[1], arc["pos"])

        obs.update(t=11, pickups=[])
        self.bot.act(obs)
        self.assertEqual(self.bot.steer.call_args.args[1], [100, 0])

    def test_keeps_lightning_during_local_encounters(self):
        gear = [self.gun, self.lightning]
        items = [self.arc, self.laser]
        self.assertEqual(self.bot.secondary_upgrades(gear, items, 46), [])
        self.assertEqual(self.bot.secondary_upgrades(gear, items, 48), [self.laser])

    def test_preserves_primary_and_never_replaces_an_empty_slot(self):
        items = [self.laser, self.arc]
        self.assertEqual(self.bot.secondary_upgrades([self.gun, self.mortar], items, 90), items)
        for gear in ([self.gun, None], [None, self.mortar], [self.lightning, self.mortar]):
            self.assertEqual(self.bot.secondary_upgrades(gear, items, 90), [])

    def test_waypoints_respect_ring_height_and_extra_distance(self):
        zone = {"center": [0, 0], "radius": 50}
        goal = [80, 0]
        rejected = [dict(self.laser, pos=p) for p in ([20, 0, 7], [49, 0, 0], [0, 40, 0])]
        self.assertIsNone(self.bot.upgrade_waypoint([0, 0, 0], goal, zone, rejected))
        self.assertEqual(self.bot.upgrade_waypoint([0, 0, 0], goal, zone, rejected + [self.laser]),
                         self.laser["pos"])


if __name__ == "__main__":
    unittest.main()
