"""Regression coverage for stalls at the edges of a measured launch."""
from datetime import datetime, timezone
import unittest

from cold_boot import accepted_frames, window
from first_room import SessionFailed


def trace(offset):
    return f"2026-11-26T00:00:01Z INFO victory_bench: accepted present since_first_us={offset}"


class ColdBootTests(unittest.TestCase):
    launched = datetime(2026, 11, 26, tzinfo=timezone.utc)

    def test_edges_count_against_fps(self):
        frames = accepted_frames([trace(t) for t in (0, 50_000, 200_000, 250_000, 2_000_000)], self.launched)
        r = window(frames, 0, 3_000_000)
        self.assertEqual(r["frames"], 4)
        self.assertEqual(r["fps"], 4 / 3)
        self.assertEqual(r["longest_ms"], 1750)
        self.assertEqual(r["holds_over_ms"], {50: 3, 100: 3, 250: 2, 1000: 1})
        self.assertAlmostEqual(r["seconds_in_holds_over_100ms"], 2.9)
        self.assertEqual(window(frames, 1_000_000, 1_050_000)["frames"], 1)

    def test_full_window_without_a_frame(self):
        r = window([1_000_000, 10_000_000], 2_000_000, 5_000_000)
        self.assertEqual(r["fps"], 0)
        self.assertEqual(r["p99_ms"], 3000)
        self.assertEqual(r["seconds_in_holds_over_100ms"], 3)

    def test_rejects_incomplete_or_unordered_trace(self):
        for offsets in ([], [10], [0, 200, 150], ["bad"]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                accepted_frames([trace(t) for t in offsets], self.launched)

    def test_terminal_failure_invalidates_even_earlier_frames(self):
        with self.assertRaises(SessionFailed):
            accepted_frames([trace(0), "VIctory: unhandled exception 0xc0000005"], self.launched)


if __name__ == "__main__":
    unittest.main()
