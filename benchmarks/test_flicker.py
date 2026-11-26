import unittest

import numpy as np

from flicker import reversals


class FlickerTests(unittest.TestCase):
    def test_return_after_a_held_frame(self):
        frames = np.array([[2, 253], [200, 224], [200, 224], [5, 240]], dtype=np.uint8)
        self.assertEqual(list(reversals(frames)), [(1, .5)])

    def test_permanent_change_and_smooth_fade(self):
        frames = np.array([[200, 3], [80, 30], [81, 60]], dtype=np.uint8)
        self.assertEqual(list(reversals(frames)), [(1, 0.0)])
