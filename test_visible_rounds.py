import copy
import unittest
from unittest.mock import patch

from bot import Bot


class VisibleRoundsTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0, "config": {}})
        self.bot.arena.blocked.return_value = False
        me = {"id": 0, "grounded": True, "pos": [0, 0, 0], "vel": [0, 0, 0],
              "energy": 100, "weapons": [], "stats": {"radius": 2.5, "height": 9,
              "walk_speed": 11.7, "boost_speed": 19.5, "ground_accel": 58.5}}
        self.shot = {"id": 50, "kind": "gun", "pos": [-95, 0, 4.5], "vel": [252, 0, 0]}
        self.obs = {"self": me, "projectiles": [self.shot], "drops": [],
                    "zone": {"center": [0, 0], "radius": 200}}
        self.action = {"move": [1, 0], "jump": False, "boost": False,
                       "fire": [True, False], "aim": [0, 0]}

    def test_steps_sideways_for_an_incoming_round_and_continues_firing(self):
        self.bot.avoid_visible_round(self.obs, self.action)
        self.assertEqual(self.action["move"][0], 0)
        self.assertEqual(abs(self.action["move"][1]), 1)
        self.assertTrue(self.action["boost"])
        self.assertEqual(self.action["fire"], [True, False])
        self.assertEqual(self.action["aim"], [0, 0])

    def test_keeps_course_for_a_miss_or_a_departing_round(self):
        for pos, vel in (([-95, 14, 4.5], [252, 0, 0]), ([-95, 0, 4.5], [-252, 0, 0]),
                         ([-95, 0, 18], [252, 0, 0]), ([-1, 0, 15], [0, 0, -252])):
            with self.subTest(pos=pos, vel=vel):
                self.shot.update(pos=pos, vel=vel)
                before = copy.deepcopy(self.action)
                self.bot.avoid_visible_round(self.obs, self.action)
                self.assertEqual(before, self.action)

    def test_holds_an_active_supply_capture_and_keeps_safe_terrain(self):
        before = copy.deepcopy(self.action)
        self.obs["drops"] = [{"holder": 0, "progress": 3}]
        self.bot.avoid_visible_round(self.obs, self.action)
        self.assertEqual(before, self.action)
        self.obs["drops"] = []
        self.bot.arena.blocked.return_value = True
        self.bot.avoid_visible_round(self.obs, self.action)
        self.assertEqual(before, self.action)

    def test_uses_a_walk_when_boost_energy_is_low(self):
        self.obs["self"]["energy"] = 12
        self.bot.avoid_visible_round(self.obs, self.action)
        self.assertFalse(self.action["boost"])
        self.assertEqual(abs(self.action["move"][1]), 1)


if __name__ == "__main__":
    unittest.main()
