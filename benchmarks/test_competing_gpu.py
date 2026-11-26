import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from competing_gpu import busy


@unittest.skipUnless(os.name == "posix", "Linux procfs fixture uses symlinks")
class CompetingGpuTests(unittest.TestCase):
    def test_executable_survives_a_thread_rename(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / "42"
            process.mkdir()
            (process / "comm").write_text("render\n")
            (process / "exe").symlink_to("/somewhere/native_play")
            self.assertTrue(busy(root, {"native_play"}, set(), ""))

    def test_selected_group_must_hold_this_gpu(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / "43"
            (process / "fd").mkdir(parents=True)
            (process / "cgroup").write_text("0::/user.slice/other-jobs.slice/run.scope\n")
            (process / "fd/5").symlink_to("/dev/dri/renderD128")
            self.assertTrue(busy(root, set(), {"other-jobs.slice"}, "/dev/dri/renderD128"))
            self.assertFalse(busy(root, set(), {"other-jobs.slice"}, "/dev/dri/renderD129"))
            self.assertFalse(busy(root, set(), {"jobs.slice"}, "/dev/dri/renderD128"))
