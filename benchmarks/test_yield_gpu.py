import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from yield_gpu import record_overlap, rotate_trials, write_overlap, yield_timeouts


class OverlapTest(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.proc = self.root / "1234"
        self.proc.mkdir()
        self.marker = self.root / "foreground-overlap"

    def set_marker(self, path):
        (self.proc / "environ").write_bytes(b"OTHER=value\0GOAL30_YIELD_MARKER=" + os.fsencode(path) + b"\0")

    def test_marks_before_signalling(self):
        self.set_marker(self.marker)

        def check_marker(*_args):
            stamp = datetime.fromisoformat(self.marker.read_text().strip())
            self.assertIsNotNone(stamp.tzinfo)

        with (patch("yield_gpu.Path.glob", return_value=[self.proc]),
              patch("yield_gpu.scoped_timeout", return_value=True),
              patch("yield_gpu.os.pidfd_open", return_value=5),
              patch("yield_gpu.os.close"),
              patch("yield_gpu.signal.pidfd_send_signal", side_effect=check_marker) as send):
            yield_timeouts(["bench.service"])
        send.assert_called_once()

    def test_preserves_first_interruption(self):
        self.set_marker(self.marker)
        write_overlap(self.marker)
        first = self.marker.read_text()
        record_overlap(self.proc)
        self.assertEqual(self.marker.read_text(), first)

    def test_marker_is_optional(self):
        (self.proc / "environ").write_bytes(b"OTHER=value\0")
        record_overlap(self.proc)
        self.assertFalse(self.marker.exists())

    def test_ignores_other_filenames(self):
        path = self.root / "launch.json"
        self.set_marker(path)
        record_overlap(self.proc)
        self.assertFalse(path.exists())

    def test_mix_saved_and_cold_launch_dates(self):
        queue = [(mode,) for mode in ("cold-a", "fixed", "saved", "cold-b")]
        rotation = {"cold-a", "saved", "cold-b"}
        alternate = {"saved": ("saved-", "run-start")}
        for directory, marker, timestamp in (("boot-cold-a-1", "launch.json", 2),
                                             ("saved-1", "run-start", 10),
                                             ("boot-cold-b-1", "launch.json", 5)):
            path = self.root / directory / marker
            path.parent.mkdir()
            path.touch()
            os.utime(path, ns=(timestamp, timestamp))

        self.assertEqual(rotate_trials(queue, rotation, self.root, "boot-", alternate),
                         [("cold-a",), ("fixed",), ("cold-b",), ("saved",)])
        (self.root / "saved-1" / "run-start").unlink()
        self.assertEqual(rotate_trials(queue, rotation, self.root, "boot-", alternate),
                         [("saved",), ("fixed",), ("cold-a",), ("cold-b",)])
