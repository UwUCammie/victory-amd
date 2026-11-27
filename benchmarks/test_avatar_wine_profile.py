from datetime import datetime, timezone
import unittest

from avatar_wine_profile import (AVATAR_WINE_EARLY_LIMITS, AVATAR_WINE_NOTIFY_SWITCHES, AVATAR_WINE_SCREEN_LIMITS,
                                 AVATAR_WINE_WRITEBACK_SWITCHES, benchmark_flags, compute_wait_activity,
                                 early_compute_activity, early_screen_activity, observed_profile,
                                 screen_wait_coverage, verify_notification_mode, writeback_activity)
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
        for mode, value in AVATAR_WINE_WRITEBACK_SWITCHES.items():
            if value == "1":
                continue
            with self.subTest(mode=mode):
                off = benchmark_flags(mode)
                on = benchmark_flags(mode.removesuffix("off") + "on")
                self.assertEqual(off.pop("VICTORY_WC_NO_BACK"), "0")
                self.assertEqual(on.pop("VICTORY_WC_NO_BACK"), "1")
                self.assertEqual(off, on)
                self.assertEqual(on["VICTORY_WC_CENSUS"], "0")

    def test_notification_arms_change_only_the_verified_switch(self):
        shared, local = map(benchmark_flags, AVATAR_WINE_NOTIFY_SWITCHES)
        self.assertEqual(shared.pop("VICTORY_BENCH_LOCAL_PIPELINE_NOTIFY"), "0")
        self.assertEqual(local.pop("VICTORY_BENCH_LOCAL_PIPELINE_NOTIFY"), "1")
        self.assertEqual(shared, local)
        self.assertEqual(local["VICTORY_EARLY_COMPUTE_MAX_BYTES"], "2560")
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        event = "2026-11-27T08:00:01Z INFO pipeline completion notification mode local=\x1b[3mtrue\x1b[0m"
        verify_notification_mode([event], started, 2_000_000, True)
        with self.assertRaises(ValueError):
            verify_notification_mode([event], started, 2_000_000, False)
        with self.assertRaises(ValueError):
            verify_notification_mode([event], started, 1_000_000, True)

    def test_early_screen_changes_only_its_logged_byte_limit(self):
        off, enabled = map(benchmark_flags, AVATAR_WINE_SCREEN_LIMITS)
        self.assertEqual(off.pop("VICTORY_EARLY_SCREEN_MAX_BYTES"), "0")
        self.assertEqual(enabled.pop("VICTORY_EARLY_SCREEN_MAX_BYTES"), "6144")
        self.assertEqual(off, enabled)
        self.assertEqual(enabled["VICTORY_COMPUTE_WAIT_MS"], "2000")
        self.assertEqual(enabled["VICTORY_SCREEN_WAIT_MS"], "10000")
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        limit = "2026-11-27T08:00:01Z INFO cold screen pipeline byte limit bytes=6144"
        event = "2026-11-27T08:00:02Z INFO first small screen pipeline started at creation"
        self.assertEqual(early_screen_activity([limit, event], started, 3_000_000, 6144), {
            "limit_bytes": 6144, "first_early_screen_seconds": 2.0,
        })
        with self.assertRaises(ValueError):
            early_screen_activity([limit], started, 3_000_000, 6144)

    def test_wait_coverage_clips_gaps_and_does_not_double_count_threads(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        logs = [
            "2026-11-27T08:00:03Z INFO a pass over the screen was waited for ms=1800 made=true",
            "2026-11-27T08:00:02Z INFO a pass over the screen was waited for ms=1500 made=false",
            "2026-11-27T08:00:02Z INFO a compute pass was waited for ms=800 made=true",
            "2026-11-27T08:00:05Z INFO a compute pass was waited for ms=4500 made=true",
        ]
        rows = screen_wait_coverage(logs, started, 4_000_000, [1_000_000, 2_900_000, 3_500_000, 4_500_000])
        self.assertEqual(rows, [
            {"start_seconds": 1.0, "gap_ms": 1900, "screen_overlap_ms": 1900, "compute_overlap_ms": 800},
            {"start_seconds": 2.9, "gap_ms": 600, "screen_overlap_ms": 100, "compute_overlap_ms": 0},
        ])

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
        off, on, wider, shorter, larger, legacy_fma = map(benchmark_flags, AVATAR_WINE_EARLY_LIMITS)
        self.assertEqual(legacy_fma, larger)
        self.assertEqual(larger.pop("VICTORY_EARLY_COMPUTE_MAX_BYTES"), "3072")
        self.assertEqual(larger, {key: value for key, value in shorter.items()
                                  if key != "VICTORY_EARLY_COMPUTE_MAX_BYTES"})
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
