from datetime import datetime, timezone
import unittest

from avatar_wine_profile import compute_wait_activity, observed_profile
from cold_boot import verify_wait_budgets


class AvatarWineProfileTests(unittest.TestCase):
    def test_log_confirms_frame_rate_mapping_and_compute_budget(self):
        lines = [
            "frame rate: the title's read of its frame rate setting patched (VICTORY_FRAME_INTERVAL_MS) rate=\x1b[3m60\x1b[0m",
            "title pages are shown with the host's mmap, beside Wine's server (VICTORY_WINE_MAP=0: as views)",
            "renderer port 1 under Wine: the title's 32-bit graphics pages are shown as memory of their own",
            "compute passes wait for their host pipeline by a budget of their own (VICTORY_COMPUTE_WAIT_MS) millis=10000",
        ]
        self.assertEqual(observed_profile(lines), {
            "frame_rate_patched_to_60": True,
            "wine_mmap": True,
            "private_graphics_pages": True,
            "compute_wait_ms": 10000,
        })
        verify_wait_budgets(lines, compute_ms=10000)
        with self.assertRaisesRegex(ValueError, "expected 500 ms"):
            verify_wait_budgets(lines, compute_ms=500)

    def test_disabled_paths_and_unpatched_rate_stay_absent(self):
        self.assertEqual(observed_profile([
            "frame rate: the title's read of its frame rate setting patched (VICTORY_FRAME_INTERVAL_MS) rate=30",
            "title pages are shown as views in placeholders (VICTORY_WINE_MAP=0)",
        ]), {
            "frame_rate_patched_to_60": False,
            "wine_mmap": False,
            "private_graphics_pages": False,
            "compute_wait_ms": None,
        })

    def test_wait_activity_is_bounded_by_launch_window(self):
        label = "a compute pass was waited for"
        lines = [
            f"2026-11-27T08:00:00Z INFO {label} ms=\x1b[2m10000\x1b[0m made=false",
            f"2026-11-27T08:00:02Z INFO {label} ms=120 made=true",
            f"2026-11-27T08:05:00Z INFO {label} ms=11000 made=false",
        ]
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        self.assertEqual(compute_wait_activity(lines, started, 300_000_000), {
            "reports": 2,
            "without_pipeline_result": 1,
            "longest_reported_wait_ms": 10000,
        })
