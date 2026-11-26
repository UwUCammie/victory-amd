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
