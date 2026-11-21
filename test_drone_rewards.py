import unittest
from unittest.mock import patch

from bot import Bot


class DroneRewardTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0, "config": {}})
        self.point = [35, 0, 0]
        self.drone = {"id": 103, "kind": "npc", "pos": self.point, "hp": 200}
        self.me = {"pos": [0, 0, 0], "id": 2, "hp": 1400, "max_hp": 1400,
                   "cubes": 0, "weapons": [{"kind": "gun"}, None]}
        self.obs = {"self": self.me, "zone": {"center": [0, 0], "radius": 150},
                    "t": 10, "mechs": [self.drone], "crates": [], "cubes": [],
                    "pickups": [], "drops": []}
        self.bot.focus = self.drone["id"]

    def test_moves_toward_the_drone_already_engaged(self):
        self.assertEqual(self.bot.loot_goal(self.obs, 120)[1:], (self.point, False))
        self.bot.focus = 102
        self.assertIsNone(self.bot.loot_goal(self.obs, 120))

    def test_yields_to_a_rival_low_health_or_third_cube(self):
        self.assertIsNone(self.bot.loot_goal(self.obs, 65))
        self.me["hp"] = 1100
        self.assertIsNone(self.bot.loot_goal(self.obs, 120))
        self.me.update(hp=1400, cubes=3)
        self.assertIsNone(self.bot.loot_goal(self.obs, 120))

    def test_keeps_an_available_first_weapon_until_the_slot_is_filled(self):
        self.obs["pickups"] = [{"id": 8010, "kind": "laser", "pos": [55, 0, 0]}]
        self.assertEqual(self.bot.loot_goal(self.obs, 120)[1], [55, 0, 0])
        self.me["weapons"][1] = {"kind": "laser"}
        self.assertEqual(self.bot.loot_goal(self.obs, 120)[1], self.point)

    def test_drone_must_be_on_reachable_ground_inside_the_zone(self):
        for point in ([40, 0, 12], [98, 0, 0]):
            with self.subTest(point=point):
                self.drone["pos"] = point
                self.assertIsNone(self.bot.loot_goal(self.obs, 120))
        self.drone["pos"] = self.point
        self.obs["zone"]["radius"] = 40
        self.assertIsNone(self.bot.loot_goal(self.obs, 120))


if __name__ == "__main__":
    unittest.main()
