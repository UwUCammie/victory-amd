import unittest

from avatar_wine_profile import observed_profile


class AvatarWineProfileTests(unittest.TestCase):
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
