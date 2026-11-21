import unittest
from unittest.mock import patch

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
