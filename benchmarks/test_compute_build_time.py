import unittest
from compute_build_time import estimate, first_events


class BuildTimeTests(unittest.TestCase):
    def test_only_positive_matches_before_snapshot(self):
        drops = {"a": 2, "b": 10, "c": 1, "d": 1, "e": 1}
        done = {"a": 17, "b": 12, "c": 19.5, "d": 8}
        times = {"a": 2000, "b": 4000, "c": 1000}
        got = estimate(drops, done, times, 20, lambda shader: shader)
        self.assertEqual(got["matched_to_slow_build_before_snapshot"], 2)
        self.assertEqual(got["median_estimated_seconds_drop_to_build_start"], 5.5)
        self.assertEqual(got["estimated_build_start_over_10s_after_drop"], 1)

    def test_translation_must_land_inside_the_estimated_worker_interval(self):
        drops = dict.fromkeys(("a", "b", "c"), 0)
        finished = dict.fromkeys(drops, 10)
        got = estimate(drops, finished, dict.fromkeys(drops, 2000), 13, str, {"a": 9, "b": 7, "c": 11})
        self.assertEqual(got["translations_observed_within_estimated_build"], 1)
        self.assertEqual(got["median_seconds_translation_to_host_completion"], 1)
        self.assertEqual(got["median_fraction_of_build_after_translation"], 0.5)

    def test_repeated_host_messages_use_the_earliest_timestamp(self):
        log = [f"2030-01-01T00:00:0{n}Z INFO victory_gpu::pipeline::host: host pipeline shaders=[compute bbaa]"
               for n in (4, 2)]
        log.append("2030-01-01T00:00:00Z INFO victory_gpu::pipeline::make: a compute dispatch was dropped: shaders=bbaa")
        drops, done = first_events(log)
        self.assertEqual(done["bbaa"] - drops["bbaa"], 2)


if __name__ == "__main__":
    unittest.main()
