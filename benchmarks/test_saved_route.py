import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from saved_route import classify, route_outcome


class SavedRouteTests(unittest.TestCase):
    present = "2026-11-01T00:00:00Z INFO victory_bench: accepted present since_first_us=0"

    def result(self, *lines, code=124, seconds=161, overlap=False):
        return classify(lines, interrupted=overlap, exit_code=code, elapsed=seconds, target=161)

    def test_wrapper_success_cannot_hide_failure(self):
        self.assertEqual(self.result(self.present, "VIctory: unhandled exception 0x80000003", code=0), "renderer-failure")

    def test_overlap_is_excluded_even_if_termination_looks_like_a_crash(self):
        self.assertEqual(self.result("VIctory: unhandled exception 0", overlap=True), "interrupted")

    def test_distinguishes_device_failure_from_a_completed_timeout(self):
        self.assertEqual(self.result(self.present, "host GPU failure: synthetic"), "device-failure")
        self.assertEqual(self.result("VIctory: first-chance exception 0", self.present), "finished")

    def test_short_runtime_missing_trace_and_early_exit_are_incomplete(self):
        self.assertEqual(self.result(self.present, seconds=158), "incomplete")
        self.assertEqual(self.result(), "incomplete")
        self.assertEqual(self.result(self.present, code=0), "incomplete")


    def test_yield_and_missing_files_before_renderer_initializes(self):
        with TemporaryDirectory() as directory:
            run = Path(directory)
            marker = run / "overlap"
            self.assertEqual(route_outcome(run, marker, 1, 161), "incomplete")
            marker.touch()
            self.assertEqual(route_outcome(run, marker, 1, 161), "interrupted")
