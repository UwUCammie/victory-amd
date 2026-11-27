"""Regression coverage for stalls at the edges of a measured launch."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from cold_boot import accepted_frames, loaded_vkd3d_build, report, upload_pool_activity, verify_wait_budgets, window
from first_room import SessionFailed


def trace(offset):
    return f"2026-11-26T00:00:01Z INFO victory_bench: accepted present since_first_us={offset}"


class ColdBootTests(unittest.TestCase):
    def test_wait_budgets_verify_ansi_logs_and_reject_unexpected_settings(self):
        graphics = "host pipeline wait budget per frame \x1b[3mmillis\x1b[0m=\x1b[2m500\x1b[0m"
        compute = "compute dispatches wait for their pipelines \x1b[3mms\x1b[0m=\x1b[2m500\x1b[0m"
        verify_wait_budgets([graphics], graphics_ms=500, compute_ms=0)
        verify_wait_budgets([graphics, compute], graphics_ms=500, compute_ms=500)
        for lines, wait in (([graphics], 500), ([graphics, compute], 0),
                            ([graphics, compute.replace("500", "5000")], 500)):
            with self.subTest(lines=lines, wait=wait), self.assertRaisesRegex(ValueError, "compute waits"):
                verify_wait_budgets(lines, graphics_ms=500, compute_ms=wait)
        with self.assertRaisesRegex(ValueError, "graphics waits"):
            verify_wait_budgets([compute], graphics_ms=500, compute_ms=500)
        with self.assertRaisesRegex(ValueError, "compute wait announcement"):
            verify_wait_budgets([graphics, "compute dispatches wait for their pipelines secs=10"], compute_ms=0)

    def test_driver_build_verifies_loaded_revision_and_rejects_mixed_logs(self):
        old = "info: vkd3d-proton - build: abcd012345+ (custom)."
        new = "info: vkd3d-proton - build: 98765432."
        version = "vkd3d-proton - applicationVersion: 3.2.0"
        self.assertEqual(loaded_vkd3d_build([version, old, old], "ABCD012"), "abcd012345")
        for lines in ([version], [new], [old, new], [old, "vkd3d-proton - build: unknown"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                loaded_vkd3d_build(lines, "abcd012")

    launched = datetime(2026, 11, 26, tzinfo=timezone.utc)

    def test_upload_pool_counters_use_latest_sample_before_the_cutoff(self):
        enabled = "2026-11-26T00:00:01Z INFO list upload pool (\x1b[3mVICTORY_UPLOAD_POOL=1\x1b[0m)"
        sample = (
            "2026-11-26T00:00:03Z INFO their buffers used again (VICTORY_VIEW_POOL=0): "
            "8 taken from the pool, 9 put in, 2 MB in it now"
        )
        mapped = (
            "2026-11-26T00:00:02.8Z INFO new card memory waited for until it is mapped "
            "(VICTORY_WAIT_RESIDENT=0: not), since the start: 8 times, 5.1 ms, the longest 1.4 ms"
        )
        later = sample.replace("00:00:03", "00:00:05").replace("8 taken", "12 taken")
        older = sample.replace("00:00:03", "00:00:02").replace("8 taken", "5 taken")
        result = upload_pool_activity([enabled, sample, mapped, later, older], self.launched, 5_000_000, 1)
        self.assertEqual(result, {
            "enabled": True,
            "pool": {"sample_seconds": 3, "taken": 8, "returned": 9, "retained_mib": 2},
            "mapping": {"sample_seconds": 2.8, "waits": 8, "summed_ms": 5.1, "longest_ms": 1.4},
        })
        disabled = enabled.replace("POOL=1", "POOL=0")
        self.assertEqual(upload_pool_activity([disabled], self.launched, 5_000_000, 0),
                         {"enabled": False, "pool": None, "mapping": None})
        for lines, switch in (([sample], 1), ([enabled], 0), ([enabled, disabled], 1),
                              ([enabled, sample.replace("VIEW_POOL=0", "VIEW_POOL=1")], 1),
                              ([disabled, sample], 0)):
            with self.subTest(lines=lines, switch=switch), self.assertRaises(ValueError):
                upload_pool_activity(lines, self.launched, 5_000_000, switch)

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

    def test_stall_reports_use_half_open_edges_and_log_time(self):
        notice = " INFO victory_gpu::pipeline::make: a compute dispatch was dropped: its pipeline is not made"
        drops = []
        lines = [trace(0), "2026-11-26T00:00:03Z" + notice, "2026-11-26T00:00:01.5Z" + notice,
                 "2026-11-26T00:00:01Z" + notice, trace(2_000_000)]
        frames = accepted_frames(lines, self.launched, drops)
        result = window(frames, 0, 4_000_000, stalls=3, compute_drops=drops)
        self.assertEqual(result["largest_gaps"], [
            {"start_s": 1, "stop_s": 3, "gap_ms": 2000, "compute_drop_reports": 2,
             "first_compute_drop_after_gap_start_s": 0},
            {"start_s": 0, "stop_s": 1, "gap_ms": 1000, "compute_drop_reports": 0,
             "first_compute_drop_after_gap_start_s": None},
            {"start_s": 3, "stop_s": 4, "gap_ms": 1000, "compute_drop_reports": 1,
             "first_compute_drop_after_gap_start_s": 0},
        ])
        self.assertEqual(window(frames, 0, 4_000_000, stalls=1, compute_drops=[1_500_000])
                         ["largest_gaps"][0]["first_compute_drop_after_gap_start_s"], 0.5)
        self.assertNotIn("largest_gaps", window(frames, 0, 4_000_000))
        with self.assertRaises(ValueError):
            window(frames, 0, 4_000_000, stalls=-1)

    def test_rejects_incomplete_or_unordered_trace(self):
        for offsets in ([], [10], [0, 200, 150], ["bad"]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                accepted_frames([trace(t) for t in offsets], self.launched)

    def test_compute_gap_count_includes_both_window_edges_and_excludes_stop(self):
        result = window([1_000_000, 4_000_000], 0, 6_000_000, compute_gap_ms=2000,
                        compute_drops=[6_000_000, 1_000_000, 999_999])
        self.assertEqual(result["long_gap_compute_drops"], {
            "threshold_ms": 2000, "gaps": 2, "gaps_with_notice": 1, "seconds_in_gaps": 5,
        })
        result = window([1_000_000, 4_000_000], 0, 6_000_000, compute_gap_ms=1000,
                        compute_drops=[6_000_000, 1_000_000, 999_999])
        self.assertEqual(result["long_gap_compute_drops"]["gaps_with_notice"], 2)
        self.assertNotIn("largest_gaps", result)
        with self.assertRaisesRegex(ValueError, "threshold"):
            window([1_000_000], 0, 2_000_000, compute_gap_ms=0)

    def test_verifies_host_output_at_creation_and_resize(self):
        create = "INFO victory_gpu::host: presenting to a window width=1280 height=720 format=28"
        resize = "INFO victory_gpu::host: the swap chain's buffers were made again for another size or format "
        hint = 'INFO victory_loader::resolution: settings value="1280x720 scene, 3840x2160 interface"'
        expected = (1280, 720)
        frames = [trace(0), trace(10)]
        self.assertEqual(accepted_frames([create, *frames, resize + "height=720 width=1280"],
                                         self.launched, expected_output=expected), [1_000_000, 1_000_010])
        for lines in ([hint, *frames], [create.replace("720", "1080"), *frames],
                      [create, *frames, resize + "width=1920 height=1080"], [create.rsplit(" height=", 1)[0], *frames],
                      [*frames, create], [resize + "width=1280 height=720", *frames]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                accepted_frames(lines, self.launched, expected_output=expected)

    def test_live_window_requires_a_present_at_or_after_its_end(self):
        with TemporaryDirectory() as work:
            run = Path(work)
            meta = run / "launch.json"
            launch = {"start_utc": self.launched.isoformat(), "timeout": 5, "story_slots": 0,
                      "empty_cache_directories": dict.fromkeys(("cache", "vkd3dcache", "mesa", "xdg", "dxvk"), 0)}
            meta.write_text(json.dumps(launch))
            log = run / "run.log"
            log.write_text(trace(0) + "\n")
            with self.assertRaisesRegex(ValueError, "not yet covered"):
                report(run, meta, 0, 2_000_000, progress=True)
            with self.assertRaises(FileNotFoundError):
                report(run, meta, 0, 2_000_000)
            log.write_text(trace(0) + "\n" + trace(1_000_000) + "\n" + trace("partial"))
            preview = report(run, meta, 0, 2_000_000, progress=True)
            self.assertTrue(preview.pop("provisional"))
            (run / "foreground-overlap").touch()
            with self.assertRaisesRegex(ValueError, "overlap"):
                report(run, meta, 0, 2_000_000, progress=True)
            (run / "foreground-overlap").unlink()
            log.write_text(trace(0) + "\n" + trace(1_000_000) + "\n")
            (run / "exit-code").write_text("124")
            with self.assertRaisesRegex(ValueError, "final launcher metadata"):
                report(run, meta, 0, 2_000_000, progress=True)
            launch["end_utc"] = self.launched.replace(second=5).isoformat()
            meta.write_text(json.dumps(launch))
            self.assertEqual(preview, report(run, meta, 0, 2_000_000))

    def test_terminal_failure_invalidates_even_earlier_frames(self):
        with self.assertRaises(SessionFailed):
            accepted_frames([trace(0), "VIctory: unhandled exception 0xc0000005"], self.launched)

    def test_interface_requires_success_at_the_output_site_before_present(self):
        host = "INFO victory_gpu::host: presenting to a window width=1280 height=720"
        applied = ('INFO victory_loader::resolution: resolution: patched site=example '
                   'what="settings\' output size applied" value="1280x720 scene, 3840x2160 interface"')
        failed = "resolution: settings' output size applied (1280x720 scene, 3840x2160 interface) at title+0: Differs"
        sizes = dict(expected_output=(1280, 720), expected_interface=(3840, 2160))
        self.assertEqual(accepted_frames([applied, host, trace(0)], self.launched, **sizes), [1_000_000])
        for lines in ([host, trace(0)], [failed, host, trace(0)], [host, trace(0), applied],
                      [applied.replace("3840x2160", "1920x1080"), host, trace(0)],
                      [applied.replace("output size applied", "other site"), host, trace(0)],
                      [applied.replace("resolution: patched", "resolution: not patched"), host, trace(0)]):
            with self.subTest(lines=lines), self.assertRaisesRegex(ValueError, "interface setup"):
                accepted_frames(lines, self.launched, **sizes)
        with self.assertRaisesRegex(ValueError, "host output"):
            accepted_frames([applied, trace(0)], self.launched, expected_interface=(3840, 2160))


if __name__ == "__main__":
    unittest.main()
