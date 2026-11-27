from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from avatar_wine_profile import (AVATAR_WINE_BOOL_SIMPLIFY, AVATAR_WINE_COMPILER_CACHE, AVATAR_WINE_CONSTRUCTOR_POOLS, AVATAR_WINE_EARLY_LIMITS, AVATAR_WINE_FACE_EARLY_LIMITS, AVATAR_WINE_FACE_TRACE, AVATAR_WINE_FACE_TRACE_EARLY, AVATAR_WINE_FACE_WORKER_COUNTS, AVATAR_WINE_FACES, AVATAR_WINE_FACES_2S, AVATAR_WINE_FACES_EARLY, AVATAR_WINE_FACES_HALF_FIX, AVATAR_WINE_FACES_OFF, AVATAR_WINE_KEEP_TRANSLATED, AVATAR_WINE_LATEST_CONTROL, AVATAR_WINE_LATEST_SHADERS,
                                 AVATAR_WINE_NOTIFY_SWITCHES, AVATAR_WINE_PIPELINE_INPUTS, AVATAR_WINE_SCREEN_LIMITS, AVATAR_WINE_SCREEN_QUEUE_10S, AVATAR_WINE_SCREEN_QUEUE_PRIORITY, AVATAR_WINE_SCREEN_QUEUE_TRACE, AVATAR_WINE_SINGLE_PARSE, AVATAR_WINE_STAGE_CPU_PROFILE, AVATAR_WINE_STAGE_INDEX_PROFILE,
                                 AVATAR_WINE_QUEUE_TIMING, AVATAR_WINE_QUEUE_TIMINGS, AVATAR_WINE_SCREEN_WORKERS, AVATAR_WINE_VALUE_USE_INDEX, AVATAR_WINE_WAITER_SWITCHES,
                                 AVATAR_WINE_WRITEBACK_SWITCHES, benchmark_flags, compute_wait_activity,
                                 early_compute_activity, early_screen_activity, observed_profile,
                                 pipeline_stage_activity, pipeline_wait_gap_totals, pipeline_wait_group_coverage, pipeline_wait_translation_coverage,
                                 screen_wait_coverage, screen_worker_activity,
                                 queue_claim_activity, verify_constructor_pool, verify_notification_mode, verify_pipeline_workers, verify_waiter_priority, writeback_activity)
from cold_boot import verify_wait_budgets
from avatar_wine_profile import AVATAR_WINE_CARD_TOUCHED, AVATAR_WINE_SCREEN_WAIT_BOUNDARIES, screen_wait_progress, verify_card_dirty_scan
from avatar_wine_profile import AVATAR_WINE_CAPTURE_OBSERVERS, AVATAR_WINE_MERGED_COLD, AVATAR_WINE_OBSERVERS_OFF, AVATAR_WINE_OBSERVERS_ON, verify_capture_observers
from avatar_wine_profile import AVATAR_WINE_SCREEN_WAITER_DIAGNOSTICS, AVATAR_WINE_SCREEN_WAITER_SCORES, verify_screen_waiter_priority
from avatar_wine_profile import AVATAR_WINE_WRITE_WATCH_GAPS, verify_write_watch_gap
from avatar_wine_profile import AVATAR_WINE_RECORDED_COMPUTE, recorded_compute_activity


class AvatarWineProfileTests(unittest.TestCase):
    def test_recorded_compute_pair_changes_only_lookahead_and_clips_replay(self):
        for arm, value in AVATAR_WINE_RECORDED_COMPUTE.items():
            self.assertEqual(benchmark_flags(arm), dict(benchmark_flags(AVATAR_WINE_MERGED_COLD),
                                 VICTORY_EARLY_RECORDED_COMPUTE=value, VICTORY_RECORDED_COMPUTE_TRACE="1"))
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = [
            "2026-11-27T08:00:00Z INFO recorded compute pipeline lookahead enabled=true trace=true",
            "2026-11-27T08:00:01Z INFO first recorded compute pipeline queued before replay",
            "2026-11-27T08:00:02Z INFO recorded compute pipeline reached replay us=150000 ready=true",
            "2026-11-27T08:00:03Z INFO recorded compute pipeline reached replay us=40000 ready=false",
            "2026-11-27T08:00:04Z INFO recorded compute pipeline reached replay us=400000 ready=true",
        ]
        self.assertEqual(recorded_compute_activity(lines, start, 4_000_000, True), {
            "count": 2, "ready_at_first_replay": 1, "lead_median_us": 95_000,
            "lead_p95_us": 150_000, "lead_max_us": 150_000, "lead_over_100ms": 1,
            "first_queued_us": 1_000_000,
        })
        with self.assertRaises(ValueError):
            recorded_compute_activity(lines, start, 4_000_000, False)

    def test_write_watch_gap_pair_uses_the_same_cold_profile(self):
        for mode, gap in AVATAR_WINE_WRITE_WATCH_GAPS.items():
            self.assertEqual(benchmark_flags(mode), dict(benchmark_flags(AVATAR_WINE_MERGED_COLD),
                             VICTORY_AHEAD_GAP_KIB=str(gap)))
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = ["2026-11-27T08:00:01Z INFO write-watch join gap kib=1024"]
        verify_write_watch_gap(lines, start, 2_000_000, 1024)
        with self.assertRaises(ValueError):
            verify_write_watch_gap(lines, start, 2_000_000, 8192)

    def test_observer_pair_uses_the_same_runtime_flags(self):
        off = benchmark_flags(AVATAR_WINE_OBSERVERS_OFF)
        self.assertEqual(off, benchmark_flags(AVATAR_WINE_OBSERVERS_ON))
        self.assertEqual(off, benchmark_flags(AVATAR_WINE_MERGED_COLD))
        self.assertEqual(off, benchmark_flags(next(iter(AVATAR_WINE_CARD_TOUCHED))))
        self.assertFalse(AVATAR_WINE_CAPTURE_OBSERVERS[AVATAR_WINE_MERGED_COLD])

    def test_observer_modes_require_matching_metadata_and_outputs(self):
        with TemporaryDirectory() as directory:
            captures = Path(directory)
            off = {"capture_observers": [], "runtime_capture": "0"}
            on = dict(off, capture_observers=["stills", "clip"])
            verify_capture_observers(off, captures, False)
            with self.assertRaises(ValueError):
                verify_capture_observers(on, captures, True)
            (captures / "private-25.png").write_bytes(b"still")
            (captures / "private-dialogue.mkv").write_bytes(b"clip")
            verify_capture_observers(on, captures, True)
            with self.assertRaises(ValueError):
                verify_capture_observers(on, captures, True, complete=True)
            verify_capture_observers(dict(on, capture_observer_exit_codes={"clip": 0}),
                                     captures, True, complete=True)
            with self.assertRaises(ValueError):
                verify_capture_observers(off, captures, False)
            with self.assertRaises(ValueError):
                verify_capture_observers(dict(on, runtime_flags={"VICTORY_CAPTURE_WORLD": "0"}),
                                         captures, True)

    def test_card_touched_pair_keeps_writeback_and_profile_fixed(self):
        for mode, switch in AVATAR_WINE_CARD_TOUCHED.items():
            self.assertEqual(benchmark_flags(mode),
                             dict(benchmark_flags(AVATAR_WINE_FACES_EARLY), VICTORY_CARD_TOUCHED=switch,
                                  VICTORY_WC_NO_BACK="0", VICTORY_WC_KEEP_STORES="0"))

    def test_card_touched_requires_a_matching_runtime_marker_in_window(self):
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = ["2026-11-27T08:00:01Z INFO card copy dirty scan mode enabled=\x1b[3mtrue\x1b[0m"]
        verify_card_dirty_scan(lines, start, 2_000_000, True)
        for marker, stop, enabled in ((lines, 2_000_000, False), (lines, 500_000, True),
                                      (lines * 2, 2_000_000, True)):
            with self.assertRaises(ValueError):
                verify_card_dirty_scan(marker, start, stop, enabled)

    def test_face_build_keeps_the_cold_profile_with_raw_loads_explicit(self):
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES),
                         dict(benchmark_flags(AVATAR_WINE_LATEST_SHADERS), VICTORY_RAW_TYPED_LOADS="1"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_OFF),
                         dict(benchmark_flags(AVATAR_WINE_FACES), VICTORY_EARLY_COMPUTE_MAX_BYTES="0"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_EARLY),
                         dict(benchmark_flags(AVATAR_WINE_FACES_OFF), VICTORY_EARLY_COMPUTE_MAX_BYTES="3072"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_2S),
                         dict(benchmark_flags(AVATAR_WINE_FACES_EARLY), VICTORY_COMPUTE_WAIT_MS="2000"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACES_HALF_FIX), benchmark_flags(AVATAR_WINE_FACES_EARLY))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACE_TRACE), benchmark_flags(AVATAR_WINE_FACES_OFF))
        self.assertEqual(benchmark_flags(AVATAR_WINE_FACE_TRACE_EARLY), benchmark_flags(AVATAR_WINE_FACES_EARLY))
        self.assertEqual(benchmark_flags(AVATAR_WINE_PIPELINE_INPUTS), benchmark_flags(AVATAR_WINE_FACES_EARLY))
        for mode, count in AVATAR_WINE_FACE_WORKER_COUNTS.items():
            self.assertEqual(benchmark_flags(mode),
                             dict(benchmark_flags(AVATAR_WINE_FACES_EARLY), VICTORY_PIPELINE_WORKERS=str(count)))

    def test_screen_queue_trace_uses_the_same_playback_flags(self):
        for trace, control in ((AVATAR_WINE_SCREEN_QUEUE_TRACE, AVATAR_WINE_FACES_2S),
                               (AVATAR_WINE_SCREEN_QUEUE_10S, AVATAR_WINE_FACES_EARLY)):
            self.assertEqual(benchmark_flags(trace),
                             dict(benchmark_flags(control), VICTORY_PIPELINE_WAITERS_FIRST="0",
                                  VICTORY_PIPELINE_QUEUE_TIMING="1", VICTORY_PIPELINE_STAGE_TIMING="1"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_SCREEN_QUEUE_PRIORITY),
                         dict(benchmark_flags(AVATAR_WINE_SCREEN_QUEUE_10S), VICTORY_PIPELINE_WAITERS_FIRST="1"))
        self.assertEqual(benchmark_flags(AVATAR_WINE_SCREEN_WAIT_BOUNDARIES),
                         benchmark_flags(AVATAR_WINE_SCREEN_QUEUE_10S))
        for mode, setting in AVATAR_WINE_SCREEN_WAITER_DIAGNOSTICS.items():
            self.assertEqual(benchmark_flags(mode),
                             dict(benchmark_flags(AVATAR_WINE_SCREEN_QUEUE_10S),
                                  VICTORY_PIPELINE_WAITERS_FIRST=setting))

    def test_screen_waiter_priority_uses_the_runtime_marker(self):
        start = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = ["2026-11-27T08:00:01Z INFO pipeline priority for active waiters enabled=false screen_only=true"]
        verify_screen_waiter_priority(lines, start, 2_000_000, True)
        verify_waiter_priority(lines, start, 2_000_000, False)
        with self.assertRaises(ValueError):
            verify_screen_waiter_priority(lines, start, 2_000_000, False)
        with self.assertRaises(ValueError):
            verify_screen_waiter_priority([lines[0].replace("enabled=false", "enabled=true")], start, 2_000_000, True)

    def test_full_screen_priority_pair_changes_only_the_priority(self):
        for mode, switch in AVATAR_WINE_SCREEN_WAITER_SCORES.items():
            self.assertFalse(AVATAR_WINE_CAPTURE_OBSERVERS[mode])
            self.assertEqual(benchmark_flags(mode), dict(benchmark_flags(AVATAR_WINE_MERGED_COLD),
                             VICTORY_PIPELINE_WAITERS_FIRST=switch, VICTORY_PIPELINE_QUEUE_TIMING="0",
                             VICTORY_PIPELINE_STAGE_TIMING="0"))

    def test_screen_wait_uses_pipeline_key_when_two_pipelines_share_shaders(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = [
            '2026-11-27T08:00:03Z INFO a requested pipeline reached a worker us=2000000 shaders=[vertex a, pixel b] key="ab"',
            '2026-11-27T08:00:04Z INFO a requested pipeline reached a worker us=800000 shaders=[vertex a, pixel b] key="ba"',
            '2026-11-27T08:00:04Z INFO a pass over the screen was waited for ms=2000 made=true shaders=[vertex a, pixel b] key="ab"',
        ]
        result = queue_claim_activity(lines, started, 6_000_000, [1_000_000, 4_500_000], screen=True)
        self.assertEqual(result["screen_wait_reports"], 1)
        self.assertEqual(result["matched_screen_wait_reports"], 1)
        self.assertEqual(result["queued_screen_overlap_seconds"], 1)

    def test_screen_waits_still_open_at_cutoff_are_counted_once_in_a_gap(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = [
            '2026-11-27T08:00:02Z INFO screen pipeline wait started id=0 frame=4 key="ab"',
            '2026-11-27T08:00:03Z INFO screen pipeline wait started id=1 frame=4 key="ab"',
            '2026-11-27T08:00:04Z INFO screen pipeline wait ended id=1',
            '2026-11-27T08:00:04Z INFO screen pipeline wait started id=2 frame=4 key="bc"',
            '2026-11-27T08:00:07Z INFO screen pipeline wait ended id=0',
        ]
        frames = [1_000_000, 5_000_000, 6_500_000]
        result = screen_wait_progress(lines, started, 6_000_000, frames)
        self.assertEqual(result, {"started": 3, "ended": 1, "open_at_cutoff": 2,
                                  "longest_open_wait_seconds": 4, "open_wait_gap_overlap_seconds": 3})
        with self.assertRaises(ValueError):
            screen_wait_progress(lines[2:], started, 6_000_000, frames)

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
        self.assertEqual(benchmark_flags(AVATAR_WINE_STAGE_CPU_PROFILE),
                         benchmark_flags(AVATAR_WINE_STAGE_INDEX_PROFILE))

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
