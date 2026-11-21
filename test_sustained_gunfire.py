import unittest
from unittest.mock import patch

from bot import Bot


class SustainedGunfireTest(unittest.TestCase):
    def setUp(self):
        with patch("bot.Arena"):
            self.bot = Bot({"map": {"dir": "."}, "slot": 0, "config": {}})
        self.rivals = [{"id": 1}, {"id": 3}]

    def hit(self, time, source, weapon="gun"):
        events = [{"type": "damaged", "by": source, "weapon": weapon}]
        return self.bot.sustained_gunfire({"t": time, "events": events}, self.rivals)

    def test_tracks_each_shooter_and_refreshes_the_response(self):
        self.assertIsNone(self.hit(1.0, 1))
        self.assertIsNone(self.hit(1.3, 3))
        self.assertEqual(self.hit(1.6, 1), self.rivals[0])
        self.assertEqual(self.hit(2.2, 1), self.rivals[0])
        self.assertEqual(self.bot.sustained_gunfire({"t": 4.0, "events": []}, self.rivals), self.rivals[0])
        self.assertIsNone(self.bot.sustained_gunfire({"t": 4.5, "events": []}, self.rivals))

    def test_early_cover_uses_only_nearby_ground(self):
        self.bot.config = {"mech": {"muzzle_height": 7}, "cubes": {"size_per_cube": 0.05}}
        self.bot.arena.step = 8
        self.bot.arena.ground = {(-2, 0): 0, (-6, 0): 0}
        self.bot.arena.clear_view.return_value = False
        me = {"pos": [0, 0, 0], "hp": 1100, "max_hp": 1400, "stats": {"height": 9, "regen_delay": 5}}
        obs = {"t": 1, "self": me, "zone": {"center": [0, 0], "radius": 150, "next_center": [0, 0]}}
        rival = {"id": 1, "pos": [80, 0, 0], "hp": 1000}
        self.assertIsNone(self.bot.shelter(obs, rival, 80))
        self.assertEqual(self.bot.shelter(obs, rival, 80, early=True), [-16, 0])
        obs["t"] = 2
        self.bot.arena.ground = {(-6, 0): 0}
        self.assertIsNone(self.bot.shelter(obs, rival, 80, early=True))
        me["hp"] = 700
        obs["t"] = 3
        self.assertEqual(self.bot.shelter(obs, rival, 80), [-48, 0])

    def test_ignores_other_damage_and_requires_a_visible_shooter(self):
        self.assertIsNone(self.hit(1, 1))
        self.assertIsNone(self.hit(1.1, 1, "laser"))
        self.assertIsNone(self.hit(1.4, None))
        self.assertIsNone(self.hit(2.4, 1))
        self.assertEqual(self.hit(2.6, 1), self.rivals[0])
        self.assertIsNone(self.bot.sustained_gunfire({"t": 2.7, "events": []}, self.rivals[1:]))


if __name__ == "__main__":
    unittest.main()
