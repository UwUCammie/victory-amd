from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from launch_profile import runtime_pid


class LaunchProfileTests(unittest.TestCase):
    def test_runtime_pid_matches_the_executable_and_the_launch_marker(self):
        with TemporaryDirectory() as tmp:
            proc = Path(tmp)
            exe = Path("/exact/runtime.exe")
            marker = Path("/launch/foreground-overlap")
            for pid, runtime, launch in (
                (100, b"/exact/runtime.exe", b"/another/foreground-overlap"),
                (101, b"/other/runtime.exe", b"/launch/foreground-overlap"),
                (102, b"/exact/runtime.exe", b"/launch/foreground-overlap"),
            ):
                entry = proc / str(pid)
                entry.mkdir()
                (entry / "cmdline").write_bytes(runtime + b"\0run\0")
                (entry / "environ").write_bytes(b"GOAL30_YIELD_MARKER=" + launch + b"\0")
            self.assertEqual(runtime_pid(proc, exe, marker), 102)
            (proc / "102" / "environ").write_bytes(b"GOAL30_YIELD_MARKER=/launch/foreground-overlap-extra\0")
            with self.assertRaises(ValueError):
                runtime_pid(proc, exe, marker)
