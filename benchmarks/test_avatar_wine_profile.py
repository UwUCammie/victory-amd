from datetime import datetime, timezone
import unittest

from avatar_wine_profile import (AVATAR_WINE_BOOL_SIMPLIFY, AVATAR_WINE_COMPILER_CACHE, AVATAR_WINE_CONSTRUCTOR_POOLS, AVATAR_WINE_EARLY_LIMITS, AVATAR_WINE_FACE_EARLY_LIMITS, AVATAR_WINE_FACE_TRACE, AVATAR_WINE_FACE_TRACE_EARLY, AVATAR_WINE_FACE_WORKER_COUNTS, AVATAR_WINE_FACES, AVATAR_WINE_FACES_2S, AVATAR_WINE_FACES_EARLY, AVATAR_WINE_FACES_OFF, AVATAR_WINE_KEEP_TRANSLATED, AVATAR_WINE_LATEST_CONTROL, AVATAR_WINE_LATEST_SHADERS,
                                 AVATAR_WINE_NOTIFY_SWITCHES, AVATAR_WINE_PIPELINE_INPUTS, AVATAR_WINE_SCREEN_LIMITS, AVATAR_WINE_SINGLE_PARSE,
                                 AVATAR_WINE_QUEUE_TIMING, AVATAR_WINE_QUEUE_TIMINGS, AVATAR_WINE_SCREEN_WORKERS, AVATAR_WINE_VALUE_USE_INDEX, AVATAR_WINE_WAITER_SWITCHES,
                                 AVATAR_WINE_WRITEBACK_SWITCHES, benchmark_flags, compute_wait_activity,
                                 early_compute_activity, early_screen_activity, observed_profile,
                                 pipeline_stage_activity, pipeline_wait_gap_totals, pipeline_wait_group_coverage, pipeline_wait_translation_coverage,
                                 screen_wait_coverage, screen_worker_activity,
                                 queue_claim_activity, verify_constructor_pool, verify_notification_mode, verify_pipeline_workers, verify_waiter_priority, writeback_activity)
from cold_boot import verify_wait_budgets


class AvatarWineProfileTests(unittest.TestCase):
    def test_face_build_keeps_the_cold_profile_with_raw_loads_explicit(self):
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES),
                         dict(benchmark_flags(AVATAR_WINE_LATEST_SHADERS), VICTORY_RAW_TYPED_LOADS="1"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_OFF),
                         dict(benchmark_flags(AVATAR_WINE_FACES), VICTORY_EARLY_COMPUTE_MAX_BYTES="0"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_EARLY),
                         dict(benchmark_flags(AVATAR_WINE_FACES_OFF), VICTORY_EARLY_COMPUTE_MAX_BYTES="3072"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_2S),
                         dict(benchmark_flags(AVATAR_WINE_FACES_EARLY), VICTORY_COMPUTE_WAIT_MS="2000"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACE_TRACE), benchmark_flags(AVATAR_WINE_FACES_OFF))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACE_TRACE_EARLY), benchmark_flags(AVATAR_WINE_FACES_EARLY))
        self.assertEqual(benchmark_flags(AVATAR_WINE_PIPELINE_INPUTS), benchmark_flags(AVATAR_WINE_FACES_EARLY))
        for mode, count in AVATAR_WINE_FACE_WORKER_COUNTS.items():
            self.assertEqual(benchmark_flags(mode),
                             dict(benchmark_flags(AVATAR_WINE_FACES_EARLY), VICTORY_PIPELINE_WORKERS=str(count)))

    def test_worker_count_requires_the_runtime_marker(self):
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = ["2026-11-27T08:00:01Z INFO pipeline workers workers=\x1b[3m6\x1b[0m"]
        verify_pipeline_workers(lines, start, 2_000_000, 6)
        with self.assertRaises(ValueError):
            verify_pipeline_workers(lines, start, 2_000_000, 14)

    def test_compute_stage_overlap_uses_unique_traces_and_unions_repeated_waits(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        phases = 'phases=[("bindings", 0), ("root_signature", 200000), ("driver_create", 400000)]'
        logs = [
            f"2026-11-27T08:00:04Z INFO host pipeline timing us=2000000 shaders=[compute a] {phases}",
            f"2026-11-27T08:00:04Z INFO host pipeline timing us=2000000 shaders=[compute b] {phases}",
            f"2026-11-27T08:00:05Z INFO host pipeline timing us=2000000 shaders=[compute b] {phases}",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=1900 made=true shaders=[compute a]",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=1500 made=true shaders=[compute a]",
            "2026-11-27T08:00:05Z INFO a compute pass was waited for ms=2500 made=false shaders=[compute b]",
        ]
        result = pipeline_stage_activity(logs, started, 6_000_000, [1_000_000, 4_500_000])
        self.assertEqual(result["compute_pipeline_traces"], 3)
        self.assertEqual(result["compute_wait_reports"], 3)
        self.assertEqual(result["matched_compute_wait_reports"], 2)
        self.assertEqual(result["overlap_by_stage_seconds"]["bindings"], 0.1)
        self.assertEqual(result["overlap_by_stage_seconds"]["root_signature"], 0.2)
        self.assertEqual(result["overlap_by_stage_seconds"]["driver_create"], 1.6)
        self.assertEqual(result["any_stage_overlap_seconds"], 1.9)
        self.assertEqual(result["driver_create_by_gap"], [{
            "start_seconds": 1,
            "end_seconds": 4.5,
            "calls": 3,
            "overlapping_worker_seconds": 4.3,
            "peak_concurrent_calls": 3,
        }])

    def test_shader_source_comparisons_use_reference_flags(self):
        for mode in (AVATAR_WINE_VALUE_USE_INDEX, AVATAR_WINE_KEEP_TRANSLATED,
                     AVATAR_WINE_SINGLE_PARSE, AVATAR_WINE_COMPILER_CACHE, AVATAR_WINE_BOOL_SIMPLIFY,
                     AVATAR_WINE_LATEST_CONTROL, AVATAR_WINE_LATEST_SHADERS):
            with self.subTest(mode=mode):
                self.assertEqual(benchmark_flags(mode), benchmark_flags("vkd3d-master-avatar-wine-440"))

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

    def test_screen_worker_arms_require_the_requested_worker_and_claim(self):
        shared, reserved = map(benchmark_flags, AVATAR_WINE_SCREEN_WORKERS)
        self.assertEqual(shared.pop("VICTORY_RESERVE_SCREEN_WORKER"), "0")
        self.assertEqual(reserved.pop("VICTORY_RESERVE_SCREEN_WORKER"), "1")
        self.assertEqual(shared, reserved)
        self.assertEqual(reserved["VICTORY_EARLY_SCREEN_MAX_BYTES"], "0")
        self.assertEqual(reserved["VICTORY_COMPUTE_WAIT_MS"], "2000")
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        stock = "2026-11-27T08:00:01Z INFO dedicated screen pipeline worker reserved=false"
        enabled = "2026-11-27T08:00:01Z INFO dedicated screen pipeline worker reserved=\x1b[3mtrue\x1b[0m"
        claim = "2026-11-27T08:00:02Z INFO dedicated screen pipeline worker claimed its first pass"
        self.assertEqual(screen_worker_activity([stock], start, 3_000_000, False), {
            "reserved": False, "first_claim_seconds": None,
        })
        self.assertEqual(screen_worker_activity([enabled, claim], start, 3_000_000, True), {
            "reserved": True, "first_claim_seconds": 2.0,
        })
        for lines in ([enabled], [stock, claim], [enabled, claim, claim]):
            with self.assertRaises(ValueError):
                screen_worker_activity(lines, start, 3_000_000, True)

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

    def test_wait_totals_include_boundary_gaps_and_union_of_wait_types(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        logs = [
            "2026-11-27T08:00:03Z INFO a pass over the screen was waited for ms=1500 made=true",
            "2026-11-27T08:00:02Z INFO a compute pass was waited for ms=1000 made=false",
            "2026-11-27T08:00:03.500Z INFO a compute pass was waited for ms=500 made=true",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=1000 made=true",
        ]
        self.assertEqual(pipeline_wait_gap_totals(logs, started, 4_000_000, [2_500_000, 2_600_000]), {
            "long_gap_seconds": 3.9,
            "screen_overlap_seconds": 1.4,
            "compute_overlap_seconds": 1.5,
            "either_overlap_seconds": 2.4,
        })

    def test_long_gap_wait_groups_union_reports_with_matching_shader_lists_and_classes(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        logs = [
            "2026-11-27T08:00:02.2Z INFO a compute pass was waited for ms=1200 made=true shaders=[a]",
            "2026-11-27T08:00:02.5Z INFO a compute pass was waited for ms=1000 made=true shaders=[a]",
            "2026-11-27T08:00:03Z INFO a pass over the screen was waited for ms=700 made=false shaders=[a]",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=500 made=true shaders=[b]",
            "2026-11-27T08:00:08Z INFO a compute pass was waited for ms=4000 made=true shaders=[b]",
        ]
        frames = [1_000_000, 3_000_000, 3_500_000, 4_500_000, 8_000_000]
        self.assertEqual(pipeline_wait_group_coverage(logs, started, 6_000_000, frames), {
            "gaps_at_least_one_second": 2,
            "gap_seconds": 3.0,
            "any_wait_overlap_seconds": 2.5,
            "largest_group_overlap_seconds": 2.0,
            "gaps_with_one_group_covering_at_least_80_percent": 0,
        })

    def test_wait_translation_coverage_accounts_for_the_last_stage_and_unknown_shaders(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        logs = [
            '2026-11-27T08:00:02Z INFO shader translated stage="mesh" hash=2222222222222222',
            '2026-11-27T08:00:03Z INFO shader translated stage="compute" hash=1111111111111111',
            '2026-11-27T08:00:04Z INFO shader translated stage="pixel" hash=3333333333333333',
            '2026-11-27T08:00:05Z INFO a compute pass was waited for ms=4000 made=true shaders=[compute 1111111111111111]',
            '2026-11-27T08:00:05Z INFO a pass over the screen was waited for ms=3000 made=true'
            ' shaders=[mesh 2222222222222222, pixel 3333333333333333]',
            '2026-11-27T08:00:05Z INFO a compute pass was waited for ms=500 made=false shaders=[compute 4444444444444444]',
            '2026-11-27T08:00:07Z INFO shader translated stage="compute" hash=4444444444444444',
        ]
        self.assertEqual(pipeline_wait_translation_coverage(logs, started, 6_000_000, [1_000_000, 5_000_000, 7_000_000]), {
            "translation_pending_overlap_seconds": 3.0,
            "translation_logged_overlap_seconds": 2.0,
            "translation_unknown_overlap_seconds": 0.5,
        })

    def test_waiter_priority_changes_only_one_setting_and_trace_is_independent(self):
        off, on = map(benchmark_flags, AVATAR_WINE_WAITER_SWITCHES)
        self.assertEqual(off["VICTORY_PIPELINE_QUEUE_TIMING"], "0")
        self.assertEqual(on, dict(off, VICTORY_PIPELINE_WAITERS_FIRST="1"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_QUEUE_TIMING), dict(off, VICTORY_PIPELINE_QUEUE_TIMING="1"))
        for mode, priority in AVATAR_WINE_QUEUE_TIMINGS.items():
            self.assertEqual(benchmark_flags(mode), dict(
                off, VICTORY_PIPELINE_WAITERS_FIRST=priority, VICTORY_PIPELINE_QUEUE_TIMING="1"
            ))
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        line = "2026-11-27T08:00:04Z INFO pipeline priority for active waiters enabled=true"
        verify_waiter_priority([line], started, 6_000_000, True)
        with self.assertRaises(ValueError):
            verify_waiter_priority([line], started, 6_000_000, False)

    def test_worker_claim_only_matches_unambiguous_compute_requests(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        logs = [
            "2026-11-27T08:00:03Z INFO a requested pipeline reached a worker us=2000000 shaders=[compute a]",
            "2026-11-27T08:00:03Z INFO a requested pipeline reached a worker us=1000000 shaders=[compute b]",
            "2026-11-27T08:00:04Z INFO a requested pipeline reached a worker us=1000000 shaders=[compute b]",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=2000 made=true shaders=[compute a]",
            "2026-11-27T08:00:04Z INFO a compute pass was waited for ms=2000 made=true shaders=[compute b]",
            "2026-11-27T08:00:05Z INFO a pass over the screen was waited for ms=2000 made=true shaders=[mesh c]",
        ]
        self.assertEqual(queue_claim_activity(logs, started, 6_000_000, [1_000_000, 5_000_000]), {
            "recorded_claims": 3,
            "claims_after_100ms": 3,
            "longest_claim_delay_ms": 2000.0,
            "compute_wait_reports": 2,
            "matched_compute_wait_reports": 1,
            "queued_compute_overlap_seconds": 1.0,
        })

    def test_constructor_pool_flags_and_announcement(self):
        off, on = map(benchmark_flags, AVATAR_WINE_CONSTRUCTOR_POOLS)
        self.assertEqual(off["VICTORY_LIST_POOL"], "1")
        self.assertEqual(on.pop("VICTORY_LIST_CREATE_POOL"), "1")
        self.assertEqual(off.pop("VICTORY_LIST_CREATE_POOL"), "0")
        self.assertEqual(off, on)
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        off_line = "2026-11-27T08:00:02Z INFO host list reuse at construction reuse=false"
        on_line = off_line.replace("false", "true")
        verify_constructor_pool([off_line], started, 3_000_000, False)
        verify_constructor_pool([on_line], started, 3_000_000, True)
        for lines in ([off_line], [on_line, off_line], []):
            with self.assertRaises(ValueError):
                verify_constructor_pool(lines, started, 3_000_000, True)

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
        off, on, wider, shorter, larger, legacy_fma = (
            benchmark_flags(mode)
            for mode in AVATAR_WINE_EARLY_LIMITS
            if mode not in AVATAR_WINE_FACE_EARLY_LIMITS
        )
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
