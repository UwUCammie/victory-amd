from datetime import datetime, timezone
import unittest

from shared_shader_translation import shared_shader_translation


class SharedShaderTranslationTests(unittest.TestCase):
    def test_pixel_is_eligible_after_vertex_and_each_shader_excludes_the_first_claim(self):
        started = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        a = "0000000000000001"
        b = "0000000000000002"
        pixel = "0000000000000003"
        claim = "a requested pipeline reached a worker"
        complete = "shader translated"
        lines = [
            f"2026-11-27T08:00:01Z INFO {claim} shaders=[vertex {a}, pixel {pixel}]",
            f"2026-11-27T08:00:02Z INFO {claim} shaders=[pixel {pixel}, vertex {b}]",
            f"2026-11-27T08:00:03Z INFO {complete} stage=\"vertex\" hash={a}",
            f"2026-11-27T08:00:04Z INFO {complete} stage=\"vertex\" hash={b}",
            f"2026-11-27T08:00:05Z INFO {complete} stage=\"pixel\" hash={pixel}",
            f"2026-11-27T08:00:06Z INFO {claim} shaders=[vertex {a}, pixel {pixel}]",
        ]
        self.assertEqual(shared_shader_translation(lines, started, 7_000_000), {
            "additional_claims": 1,
            "estimated_worker_seconds": 1,
            "longest_estimate_ms": 1000,
        })
