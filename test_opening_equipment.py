import unittest
from unittest.mock import patch

from bot import Bot


class OpeningEquipmentTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0, "config": {}})
        self.me = {"pos": [0, 0, 0], "weapons": [{"kind": "gun"}, None],
                   "hp": 1400, "max_hp": 1400, "stats": {"walk_speed": 11.7}}
        self.kit = {"id": 8010, "kind": "laser", "pos": [110, 0, 0]}
        self.obs = {"self": self.me, "zone": {"center": [0, 0], "radius": 560},
                    "t": 3, "pickups": [self.kit], "crates": [], "drops": [], "cubes": []}

    def test_seeks_a_visible_or_remembered_first_weapon(self):
        goal = self.bot.loot_goal(self.obs, 125)
        self.assertEqual(goal[1], self.kit["pos"])
        self.assertIn(tuple(goal[1]), self.bot.opening_gear)
        self.obs.update(t=6, pickups=[])
        self.assertEqual(self.bot.loot_goal(self.obs, 125)[1], self.kit["pos"])

    def test_keeps_existing_limits_when_a_contestant_approaches_or_time_runs_out(self):
        self.assertIsNone(self.bot.loot_goal(self.obs, 62))
        self.obs["t"] = 55
        self.assertIsNone(self.bot.loot_goal(self.obs, 130))
        self.obs["t"] = 5
        self.me["hp"] = 800
        self.assertIsNone(self.bot.loot_goal(self.obs, 130))

    def test_keeps_the_floor_ring_and_loadout_constraints(self):
        self.kit["pos"][2] = 9
        self.assertIsNone(self.bot.loot_goal(self.obs, 130))
        self.kit["pos"][2] = 0
        self.obs["zone"]["radius"] = 96
        self.assertIsNone(self.bot.loot_goal(self.obs, 130))
        self.obs["zone"]["radius"] = 560
        self.me["weapons"][1] = {"kind": "lightning"}
        self.assertIsNone(self.bot.loot_goal(self.obs, 130))

    def test_sprints_only_for_a_changed_pickup(self):
        self.kit["pos"][0] = 30
        goal = self.bot.loot_goal(self.obs, 130)
        self.assertNotIn(tuple(goal[1]), self.bot.opening_gear)
        self.obs["pickups"].append({"id": 8011, "kind": "mortar", "pos": [12, 0, 0]})
        goal = self.bot.loot_goal(self.obs, 130)
        self.assertEqual(goal[1], self.kit["pos"])
        self.assertIn(tuple(goal[1]), self.bot.opening_gear)

    def test_mortar_keeps_its_original_search_distance(self):
        self.kit["kind"] = "mortar"
        self.assertIsNone(self.bot.loot_goal(self.obs, 150))
        self.kit["pos"][0] = 40
        self.assertEqual(self.bot.loot_goal(self.obs, 150)[1], self.kit["pos"])
        self.assertNotIn(tuple(self.kit["pos"]), self.bot.opening_gear)
