import unittest
from unittest.mock import patch

from bot import Bot


class CubeRewardTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0, "config": {"cubes": {"stat_cap": 10}}})
        self.obs = {"self": {"pos": [0, 0, 0], "hp": 1200, "max_hp": 1400, "cubes": 2},
                    "t": 10, "events": [], "cubes": [], "zone": {"center": [0, 0], "radius": 200}}
        self.rival = {"id": 5, "pos": [115, 0, 1], "cubes": 3}
        self.bot.confirmed_reward(self.obs, [self.rival], True)

    def confirm(self):
        self.obs.update(t=10.1, events=[{"type": "kill", "target": 5}])
        return self.bot.confirmed_reward(self.obs, [], True)

    def test_requires_a_recent_confirmed_elimination(self):
        self.obs["events"] = [{"type": "kill", "target": 4}]
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))
        self.obs.update(t=13, events=[{"type": "kill", "target": 5}])
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))

    def test_rechecks_threats_zone_health_and_other_rewards(self):
        self.assertEqual(self.confirm(), self.rival["pos"])
        self.obs["events"] = []
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], False))
        for point in ([0, 50, 0], [140, 30, 0]):
            self.assertIsNone(self.bot.confirmed_reward(self.obs, [{"id": 4, "pos": point}], True))
        self.obs["zone"]["radius"] = 120
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))
        self.obs["zone"]["radius"] = 200
        self.obs["self"]["hp"] = 500
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))
        self.obs["self"]["hp"] = 1200
        self.obs["cubes"] = [{"pos": [5, 0, 0]}]
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))

    def test_uses_the_closest_visible_cube_and_abandons_an_empty_pile(self):
        self.confirm()
        self.obs["events"] = []
        self.obs["cubes"] = [{"pos": [118, 0, 1]}, {"pos": [110, 0, 1]}]
        self.assertEqual(self.bot.confirmed_reward(self.obs, [], True), [110, 0, 1])
        self.obs["self"]["pos"] = [85, 0, 0]
        self.obs["cubes"] = []
        self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))
        self.assertIsNone(self.bot.kill_reward)

    def test_hands_off_at_the_stat_cap_or_when_the_window_expires(self):
        for cap, time in ((10, 11), (2, 29)):
            with self.subTest(cubes=cap, time=time):
                self.obs["self"]["cubes"] = 2
                self.confirm()
                self.obs.update(t=time, events=[])
                self.obs["self"]["cubes"] = cap
                self.assertIsNone(self.bot.confirmed_reward(self.obs, [], True))
                self.assertIsNone(self.bot.kill_reward)


if __name__ == "__main__":
    unittest.main()
