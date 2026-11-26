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

    def test_stall_reports_use_half_open_edges_and_log_time(self):
        notice = " INFO victory_gpu::pipeline::make: a compute dispatch was dropped: its pipeline is not made"
        drops = []
        lines = [trace(0), "2026-11-26T00:00:03Z" + notice, "2026-11-26T00:00:01.5Z" + notice,
                 "2026-11-26T00:00:01Z" + notice, trace(2_000_000)]
        frames = accepted_frames(lines, self.launched, drops)
        result = window(frames, 0, 4_000_000, stalls=2, compute_drops=drops)
        self.assertEqual(result["largest_gaps"], [
            {"start_s": 1, "stop_s": 3, "gap_ms": 2000, "compute_drop_reports": 2},
            {"start_s": 0, "stop_s": 1, "gap_ms": 1000, "compute_drop_reports": 0},
        ])
        self.assertNotIn("largest_gaps", window(frames, 0, 4_000_000))
        with self.assertRaises(ValueError):
            window(frames, 0, 4_000_000, stalls=-1)

    def test_rejects_incomplete_or_unordered_trace(self):
        for offsets in ([], [10], [0, 200, 150], ["bad"]):
            with self.subTest(offsets=offsets), self.assertRaises(ValueError):
                accepted_frames([trace(t) for t in offsets], self.launched)

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
