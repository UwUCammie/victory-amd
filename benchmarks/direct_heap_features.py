"""Count final shader-stage heap requirements in a local VSH2 translation cache."""
import argparse
from collections import Counter
import json
from pathlib import Path
from struct import unpack_from


def heap_requirements(dxil):
    """Read one ordered SFI0 feature chunk, following the checks in AvatarManz PR 58."""
    if len(dxil) < 32 or dxil[:4] != b"DXBC":
        return "unknown"
    version, total, parts = unpack_from("<III", dxil, 20)
    end = 32 + 4 * parts
    if version != 1 or parts > 256 or not end <= total <= len(dxil):
        return "unknown"
    features = None
    for i in range(parts):
        offset, = unpack_from("<I", dxil, 32 + 4 * i)
        if offset < end or offset + 8 > total:
            return "unknown"
        size, = unpack_from("<I", dxil, offset + 4)
        end = offset + 8 + size
        if end > total:
            return "unknown"
        if dxil[offset:offset + 4] == b"SFI0":
            if features is not None or size != 8:
                return "unknown"
            features, = unpack_from("<Q", dxil, offset + 8)
    if features is None:
        return "unknown"
    # D3D_SHADER_REQUIRES_RESOURCE_DESCRIPTOR_HEAP_INDEXING and SAMPLER_DESCRIPTOR_HEAP_INDEXING.
    return ("neither", "resource", "sampler", "both")[(features >> 25) & 3]


def cached_stage(data):
    if len(data) < 8 or data[:4] != b"VSH2":
        raise ValueError("expected a VSH2 cache entry")
    source_length, = unpack_from("<I", data, 4)
    pos = 8 + source_length
    if pos + 8 > len(data):
        raise ValueError("missing cache stage or bytecode size")
    stage, size = unpack_from("<II", data, pos)
    pos += 8
    if stage > 7 or pos + size > len(data):
        raise ValueError("invalid shader stage or truncated cache bytecode")
    return stage, heap_requirements(memoryview(data)[pos:pos + size])


def summarize(folder):
    all_stages, compute = Counter(), Counter()
    for path in folder.rglob("*"):
        if path.is_file():
            stage, flags = cached_stage(path.read_bytes())
            all_stages[flags] += 1
            if stage == 7:
                compute[flags] += 1
    if not all_stages:
        raise ValueError("no cache entries")
    return {"all_stages": dict(all_stages), "compute_stages": dict(compute)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="runtime cache/shaders directory")
    args = parser.parse_args()
    try:
        print(json.dumps(summarize(args.cache), indent=2, sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
