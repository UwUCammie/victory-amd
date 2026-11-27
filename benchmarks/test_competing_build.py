import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from competing_build import busy


def process(root, pid, name, session, args=()):
    entry = root / str(pid)
    entry.mkdir()
    (entry / "comm").write_text(name)
    (entry / "cmdline").write_bytes(b"\0".join(s.encode() for s in (name, *args)) + b"\0")
    (entry / "stat").write_text(f"{pid} ({name}) R 1 {pid} {session} 0")


class CompetingBuildTests(unittest.TestCase):
    def test_compiler_in_own_session_is_not_a_third_outside_compiler(self):
        with TemporaryDirectory() as tmp:
            proc = Path(tmp)
            process(proc, 10, "rustc", 8)
            process(proc, 11, "clang", 9)
            process(proc, 12, "cc1plus", 9)
            self.assertTrue(busy(proc))
            self.assertFalse(busy(proc, exclude_session=8))
            process(proc, 13, "rustc", 11)
            self.assertTrue(busy(proc, exclude_session=8))

    def test_parallel_build_driver_in_another_session_still_yields(self):
        with TemporaryDirectory() as tmp:
            proc = Path(tmp)
            process(proc, 10, "make", 8, ("-j8",))
            self.assertTrue(busy(proc))
            self.assertFalse(busy(proc, exclude_session=8))
            process(proc, 11, "ninja", 9, ("-j", "4"))
            self.assertTrue(busy(proc, exclude_session=8))


class GuardQuietTests(unittest.TestCase):
    def guard(self, runtime, kind, now):
        helper = Path(__file__).with_name("guard_quiet.sh")
        return subprocess.run(
            ["bash", "-c", 'source "$1" && goal30_guard_busy "$2" "$3" "$4"',
             "guard-test", helper, kind, runtime, str(now)],
            check=False,
        ).returncode

    def test_build_stamps_only_the_short_quiet_period(self):
        with TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            self.assertEqual(self.guard(runtime, "build", 0), 0)
            self.assertFalse((runtime / "goal30-verified-resource-busy").exists())
            os.utime(runtime / "goal30-verified-build-busy", (100, 100))
            self.assertEqual(self.guard(runtime, "idle", 104), 0)
            self.assertEqual(self.guard(runtime, "idle", 105), 1)

    def test_gpu_quiet_period_survives_a_later_build(self):
        with TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            self.assertEqual(self.guard(runtime, "gpu", 0), 0)
            gpu = runtime / "goal30-verified-resource-busy"
            os.utime(gpu, (100, 100))
            self.assertEqual(self.guard(runtime, "build", 0), 0)
            os.utime(runtime / "goal30-verified-build-busy", (120, 120))
            self.assertEqual(gpu.stat().st_mtime, 100)
            self.assertEqual(self.guard(runtime, "idle", 144), 0)
            self.assertEqual(self.guard(runtime, "idle", 145), 1)
