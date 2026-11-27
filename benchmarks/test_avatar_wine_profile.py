from datetime import datetime, timezone
import unittest

from avatar_wine_profile import (AVATAR_WINE_EARLY_LIMITS, AVATAR_WINE_WRITEBACK_SWITCHES, benchmark_flags,
                                 compute_wait_activity, early_compute_activity, observed_profile, writeback_activity)
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

    def test_writeback_arms_change_only_the_writeback_switch(self):
        off, on = map(benchmark_flags, AVATAR_WINE_WRITEBACK_SWITCHES)
        self.assertEqual(off.pop("VICTORY_WC_NO_BACK"), "0")
        self.assertEqual(on.pop("VICTORY_WC_NO_BACK"), "1")
        self.assertEqual(off, on)
        self.assertEqual(on["VICTORY_WC_CENSUS"], "0")

    def test_writeback_activity_rejects_a_wrong_mode_or_threshold(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        counters = "2026-11-27T08:00:01Z INFO title memory by what the title asked for (VICTORY_WC_STATS)"
        kept = "2026-11-27T08:00:01Z INFO shaders' writes into write-combined title memory left on the card (VICTORY_WC_NO_BACK, under 64 KiB kept), per frame: 2 declarations"
        self.assertEqual(writeback_activity([counters, kept], started, 2_000_000, True), {
            "statistics_intervals": 1, "kept_intervals": 1, "intervals_with_kept_declarations": 1,
        })
        self.assertEqual(writeback_activity([counters], started, 2_000_000, False)["kept_intervals"], 0)
        with self.assertRaises(ValueError):
            writeback_activity([counters, kept], started, 2_000_000, False)
        with self.assertRaises(ValueError):
            writeback_activity([counters, kept.replace("64 KiB", "32 KiB")], started, 2_000_000, True)

    def test_early_compute_flags_and_runtime_confirmation(self):
        off, on, wider, shorter = map(benchmark_flags, AVATAR_WINE_EARLY_LIMITS)
        self.assertEqual(shorter["VICTORY_COMPUTE_WAIT_MS"], "2000")
        self.assertEqual(dict(shorter, VICTORY_COMPUTE_WAIT_MS="10000"), wider)
        self.assertEqual(off.pop("VICTORY_EARLY_COMPUTE_MAX_BYTES"), "0")
        self.assertEqual(on.pop("VICTORY_EARLY_COMPUTE_MAX_BYTES"), "1024")
        self.assertEqual(wider.pop("VICTORY_EARLY_COMPUTE_MAX_BYTES"), "2560")
        self.assertEqual(off, on)
        self.assertEqual(off, wider)
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        limit = "2026-11-27T08:00:01Z INFO cold compute pipeline byte limit bytes=\x1b[3m1024\x1b[0m"
        event = "2026-11-27T08:00:02Z INFO first small compute pipeline started at creation"
        self.assertEqual(early_compute_activity([limit, event], started, 3_000_000, 1024), {
            "limit_bytes": 1024, "first_early_compute_seconds": 2,
        })
        self.assertEqual(early_compute_activity([limit.replace("1024", "0")], started, 3_000_000, 0), {
            "limit_bytes": 0, "first_early_compute_seconds": None,
        })
        self.assertEqual(early_compute_activity([limit.replace("1024", "2560"), event], started, 3_000_000, 2560), {
            "limit_bytes": 2560, "first_early_compute_seconds": 2,
        })
        with self.assertRaises(ValueError):
            early_compute_activity([limit, event], started, 2_000_000, 1024)
        with self.assertRaises(ValueError):
            early_compute_activity([limit, limit.replace("1024", "0"), event], started, 3_000_000, 1024)
