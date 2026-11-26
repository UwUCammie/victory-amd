"""Use synthetic events to check ordering, shader deduplication and partial logs."""
import unittest

from compute_lag import summarize


def event(second, message):
    return f"2026-11-26T00:00:{second:02}Z INFO victory_gpu::pipeline{message}"


class ComputeLagTests(unittest.TestCase):
    def test_first_drop_uses_event_time_and_only_counts_compute(self):
        bind = ': first bind stage="compute" size=1025 hash=aa'
        drop = "::make: a compute dispatch was dropped: its pipeline is not made shaders="
        translated = ': shader translated stage="compute" hash='
        result = summarize([event(1, bind), event(8, drop + "aa"), event(3, drop + "aa"),
                            event(6, translated + "aa"), event(3, translated + "bb"),
                            event(5, drop + "bb"), event(8, drop + "ff"),
                            event(7, ': shader translated stage="pixel" hash=ff')], 1024)
        self.assertEqual(result["distinct_shaders_with_drop_notice"], 3)
        self.assertEqual(result["above_early_limit"], 1)
        self.assertEqual(result["with_first_bind_size"], 1)
        self.assertEqual(result["with_translation_completion"], 2)
        self.assertEqual(result["translation_after_first_drop"], 1)
        self.assertEqual(result["median_seconds_translation_minus_first_drop"], 0.5)

    def test_no_drop_has_no_delay(self):
        self.assertIsNone(summarize([], 1024)["median_seconds_translation_minus_first_drop"])


if __name__ == "__main__":
    unittest.main()
