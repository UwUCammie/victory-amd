import unittest
from datetime import datetime, timezone

from readback_lighting import summarize


class ReadbackLightingTests(unittest.TestCase):
    def test_launch_window_groups_by_byte_width_and_reports_nonfinite_separately(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        def record(second, frame, size, values):
            return f"2026-01-01T00:00:{second:02d}Z walls trace: a read-back lands in title memory frame={frame} to=0 bytes={size} values=[{values}]"
        lines = [record(1, 2, 8, "0, 0"), record(2, 2, 8, "0, 1"), record(3, 4, 8, "NaN, 2"),
                 record(3, 4, 4, "4"), record(4, 5, 8, "0, 0")]
        data = summarize(lines, start, 1, 4)
        self.assertEqual(data[8], dict(records=3, frames=2, nonfinite_records=1, all_zero_records=1, distinct_finite_records=2))
        self.assertEqual(data[4]["records"], 1)
