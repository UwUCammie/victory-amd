"""Synthetic feature metadata for the translated-cache reader. Contains no shader code."""
from struct import pack
import unittest

from direct_heap_features import cached_stage, heap_requirements


def container(bits):
    chunk = b"SFI0" + pack("<IQ", 8, bits)
    return b"DXBC" + bytes(16) + pack("<IIII", 1, 36 + len(chunk), 1, 36) + chunk


class HeapFeatureTests(unittest.TestCase):
    def test_cache_reads_features_from_the_final_bytecode(self):
        for mask, flags in enumerate(("neither", "resource", "sampler", "both")):
            blob = container(mask << 25)
            cache = b"VSH2" + pack("<I", 5) + b"build" + pack("<II", 7, len(blob)) + blob
            self.assertEqual(cached_stage(cache), (7, flags))
            with self.assertRaises(ValueError):
                cached_stage(cache[:-1])

    def test_missing_overlapping_and_repeated_metadata_fall_back(self):
        blob = container(0)
        self.assertEqual(heap_requirements(blob.replace(b"SFI0", b"TEST")), "unknown")
        self.assertEqual(heap_requirements(blob[:32] + pack("<I", 32) + blob[36:]), "unknown")
        repeated = blob[:24] + pack("<IIII", 72, 2, 40, 56) + blob[36:] * 2
        self.assertEqual(heap_requirements(repeated), "unknown")
