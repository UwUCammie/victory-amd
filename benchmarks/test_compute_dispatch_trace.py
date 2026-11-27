from datetime import datetime, timezone
import unittest

from compute_dispatch_trace import dispatch_recording_activity


class ComputeDispatchTraceTests(unittest.TestCase):
    def test_first_unavailable_and_later_recording_are_distinct(self):
        a, b = "0000000000000001", "0000000000000002"
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        lines = [
            f'2026-11-27T08:00:01Z INFO compute dispatch trace began shader={a} attempt=1 route="direct" frame=5',
            f'2026-11-27T08:00:02Z INFO compute dispatch trace finished shader={a} attempt=1 route="direct"'
            ' frame=5 outcome="pipeline_unavailable" elapsed_us=1000000 first_recorded=false',
            f'2026-11-27T08:00:03Z INFO compute dispatch trace began shader={b} attempt=1 route="indirect" frame=5',
            f'2026-11-27T08:00:04Z INFO compute dispatch trace finished shader={a} attempt=9 route="indirect"'
            ' frame=5 outcome="recorded" elapsed_us=100 first_recorded=true',
            f'2026-11-27T08:00:06Z INFO compute dispatch trace finished shader={b} attempt=1 route="indirect"'
            ' frame=5 outcome="recorded" elapsed_us=3000000 first_recorded=true',
        ]
        result = dispatch_recording_activity(lines, started, 5_000_000, [a, b])
        self.assertEqual(result, {
            "tracked_shaders": 2,
            "shaders_attempted": 2,
            "first_attempt_outcomes": {"pipeline_unavailable": 1},
            "first_attempts_pending_at_cutoff": 1,
            "shaders_recorded": 1,
            "latest_first_recording_seconds": 4.0,
            "logged_outcomes": {"pipeline_unavailable": 1, "recorded": 1},
            "logged_routes": {"direct": 1, "indirect": 1},
        })
