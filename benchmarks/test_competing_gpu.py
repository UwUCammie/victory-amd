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

    def test_idle_inherited_client_and_a_separate_renderer(self):
        node = "/dev/dri/renderD128"
        with TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = root / "30"
            worker = root / "41"
            for process, group in [(launcher, "desktop"), (worker, "other-jobs.slice")]:
                (process / "fd").mkdir(parents=True)
                (process / "fdinfo").mkdir()
                (process / "fd/42").symlink_to(node)
                (process / "cgroup").write_text(f"0::/user.slice/{group}\n")
                (process / "fdinfo/42").write_text("drm-client-id: 61\ndrm-resident-vram: 0 KiB\n")
            (worker / "status").write_text("PPid:\t30\n")
            def occupied():
                return busy(root, set(), {"other-jobs.slice"}, node, ignore_inherited_idle=True)
            self.assertFalse(occupied())
            (worker / "fd/5").symlink_to(node)
            self.assertTrue(occupied())  # Missing telemetry.
            (worker / "fdinfo/5").write_text("drm-client-id: 70\ndrm-resident-vram: 0\n")
            self.assertTrue(occupied())  # Independent client, even before its first allocation.
            (worker / "fd/5").unlink()
            for stats in ("drm-resident-vram: 8 KiB", "drm-resident-vram: 0\ndrm-engine-gfx: 1 ns"):
                (worker / "fdinfo/42").write_text(f"drm-client-id: 61\n{stats}\n")
                self.assertTrue(occupied())
