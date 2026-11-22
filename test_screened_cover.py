import unittest
from unittest.mock import patch

from bot import Bot


class ScreenedCoverTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0,
                            "config": {"mech": {"height": 9}, "cubes": {"size_per_cube": 0.05}}})
        arena = self.bot.arena
        arena.blocked.return_value = False
        arena.nearest_cell.return_value = (0, 0)
        arena.ground = {(0, 0): 0}
        # The rival can reveal our current square by stepping to its right.
        # Moving left keeps the same wall between both avatars.
        arena.clear_view.side_effect = lambda origin, destination: origin[1] > 4 and destination[0] >= -5
        self.obs = {"t": 32, "zone": {"center": [0, 0], "radius": 180},
                    "self": {"grounded": True, "hp": 500, "pos": [0, 0, 0], "stats": {"height": 9}}}
        self.rival = {"id": 4, "hp": 1250, "pos": [50, 0, 0], "vel": [0, 9, 0], "cubes": 0}
        self.source = [50, 0, 7]
        self.bot.recent_attackers[4] = 30

    def test_steps_farther_behind_cover_when_corner_could_open(self):
        point = self.bot.screened_step(self.obs, self.rival, self.source)
        self.assertLess(point[0], -5)

    def test_holds_the_original_firing_position_against_a_wounded_rival(self):
        self.rival["hp"] = 600
        self.assertIsNone(self.bot.screened_step(self.obs, self.rival, self.source))

    def test_keeps_safe_corner_and_stays_within_ring(self):
        self.bot.arena.clear_view.side_effect = None
        self.bot.arena.clear_view.return_value = False
        self.assertIsNone(self.bot.screened_step(self.obs, self.rival, self.source))
        self.bot.arena.clear_view.side_effect = lambda origin, destination: origin[1] > 4
        self.obs["zone"]["radius"] = 8
        self.assertIsNone(self.bot.screened_step(self.obs, self.rival, self.source))

    def test_ignores_stale_alert_and_ground_blocked_by_wall(self):
        self.obs["t"] = 40
        self.assertIsNone(self.bot.screened_step(self.obs, self.rival, self.source))
        self.obs["t"] = 32
        self.bot.arena.blocked.return_value = True
        self.assertIsNone(self.bot.screened_step(self.obs, self.rival, self.source))
