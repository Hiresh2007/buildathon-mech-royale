import math
import unittest
from unittest.mock import patch

from bot import Bot


class VisibleAvatarTest(unittest.TestCase):
    def test_aim_uses_the_first_visible_part_of_the_avatar(self):
        rules = {"mech": {"height": 9}, "cubes": {"size_per_cube": 0.05}}
        target = {"kind": "mech", "id": 4, "pos": [40, 0, 0], "vel": [0, 0, 0], "cubes": 2}
        me = {
            "pos": [0, 0, 0], "aim": [0, 0],
            "stats": {"muzzle_height": 7, "min_pitch": -0.7, "max_pitch": 1.3, "radius": 2.5},
            "weapons": [{"kind": "gun", "stats": {"range": 230, "speed": 252}}, None],
        }
        observation = {"self": me, "mechs": [target], "crates": [], "t": 5}

        for ledge_height, visible_height in ((0, 4.95), (6, 8.415), (9, None)):
            with self.subTest(ledge_height=ledge_height), patch("bot.Arena") as arena:
                arena.return_value.clear_view.side_effect = lambda start, end: end[2] > ledge_height
                controller = Bot({"config": rules, "map": {"dir": "."}, "slot": 0})
                action = {}
                controller.engage(observation, action)
                if visible_height is None:
                    self.assertIsNone(controller.focus)
                    self.assertNotIn("aim", action)
                else:
                    self.assertEqual(controller.focus, target["id"])
                    self.assertAlmostEqual(action["aim"][1], math.atan2(visible_height - 7, 40))


if __name__ == "__main__":
    unittest.main()
