import unittest
from unittest.mock import patch

from bot import Bot


class IsolatedOpponentTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena") as arena:
            arena.return_value.clear_view.return_value = True
            self.bot = Bot({"config": {"mech": {"height": 9}, "cubes": {"size_per_cube": 0.05}},
                            "map": {"dir": "."}, "slot": 0})
        self.me = {"pos": [0, 0, 0], "hp": 1400, "max_hp": 1400, "stats": {"muzzle_height": 7},
                   "weapons": [{"kind": "gun"}, None]}
        self.rival = {"id": 3, "pos": [100, 0, 0], "hp": 1400, "aim": [0, 0], "cubes": 0}
        self.obs = {"self": self.me, "zone": {"center": [0, 0], "radius": 500}, "t": 30, "events": [], "alive": 15}

    def test_holds_weapon_distance_when_one_opponent_faces_away(self):
        self.assertEqual(self.bot.duel_goal(self.obs, [self.rival], True), [44, 0])
        self.assertEqual(self.bot.aim_priority, 3)
        self.me["weapons"][1] = {"kind": "lightning"}
        self.assertEqual(self.bot.duel_goal(self.obs, [self.rival], True), [68, 0])

    def test_tracks_recent_attacker_even_while_returning_to_the_circle(self):
        self.obs["events"] = [{"type": "damaged", "by": 3}]
        self.assertIsNone(self.bot.duel_goal(self.obs, [self.rival], False))
        self.obs.update(t=31, events=[])
        self.assertIsNone(self.bot.duel_goal(self.obs, [self.rival], True))

    def test_second_opponent_and_late_squad_end_the_duel(self):
        watcher = {"id": 5, "pos": [90, 20, 0], "aim": [0, 0]}
        self.assertIsNone(self.bot.duel_goal(self.obs, [self.rival, watcher], True))
        self.obs["alive"] = 5
        self.assertIsNone(self.bot.duel_goal(self.obs, [self.rival], True))


if __name__ == "__main__":
    unittest.main()
