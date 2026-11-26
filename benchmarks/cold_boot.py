"""Measure a fixed wall-time window of a cold launch, including both edges."""
import argparse
import json
import math
import re
from bisect import bisect_left
from datetime import datetime, timedelta
from heapq import nlargest
from pathlib import Path

from first_room import TIMESTAMP, session_lines

MICROSECOND = timedelta(microseconds=1)
MARKER = "victory_bench: accepted present"
TRACE = re.compile(r"victory_bench: accepted present since_first_us=(\d+)(?:\s|$)")


CREATE_SWAP_CHAIN = "victory_gpu::host: presenting to a window "
RESIZE_SWAP_CHAIN = "victory_gpu::host: the swap chain's buffers were made again for another size or format "


def output_size(value):
    if not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("expected WIDTHxHEIGHT, for example 1280x720")
    return tuple(map(int, value.split("x")))


def verify_output(lines, expected):
    """Require the host swap chain to use the expected dimensions throughout the run."""
    found = False
    for line in lines:
        if CREATE_SWAP_CHAIN in line or RESIZE_SWAP_CHAIN in line:
            width = re.search(r"\bwidth=(\d+)\b", line)
            height = re.search(r"\bheight=(\d+)\b", line)
            if not width or not height:
                raise ValueError("incomplete swap-chain dimensions")
            size = int(width[1]), int(height[1])
            if size != expected:
                raise ValueError(f"host output {size[0]}x{size[1]}, expected {expected[0]}x{expected[1]}")
            if CREATE_SWAP_CHAIN in line:
                found = True
        if not found and MARKER in line:
            raise ValueError("first accepted present precedes a verified swap-chain creation")
        yield line
    if not found:
        raise ValueError("no host swap-chain creation in the run")


def accepted_frames(lines, launched, compute_drops=None, *, expected_output=None):
    """Anchor the first accepted present to launcher UTC, then use its monotonic clock."""
    frames = []
    first = None
    records = session_lines(lines)
    if expected_output is not None:
        records = verify_output(records, expected_output)
    for line in records:
        if compute_drops is not None and "victory_gpu::pipeline::make: a compute dispatch was dropped:" in line:
            timestamp = TIMESTAMP.search(line)
            if timestamp:
                when = datetime.fromisoformat(timestamp[0].replace("Z", "+00:00"))
                compute_drops.append((when - launched) // MICROSECOND)
        if MARKER not in line:
            continue
        timestamp = TIMESTAMP.search(line)
        trace = TRACE.search(line)
        if not timestamp or not trace:
            raise ValueError("incomplete accepted-present record")
        offset = int(trace[1])
        if first is None:
            first = (datetime.fromisoformat(timestamp[0].replace("Z", "+00:00")) - launched) // MICROSECOND
            if first < 0 or offset != 0:
                raise ValueError("invalid first accepted present")
        elapsed = first + offset
        if frames and elapsed < frames[-1]:
            raise ValueError("present clock moved backwards")
        frames.append(elapsed)
    if not frames:
        raise ValueError("no accepted-present trace")
    return frames


def window(frames, start, stop, *, stalls=0, compute_drops=()):
    """Times in microseconds. A present at start counts. One at stop does not."""
    if not 0 <= start < stop:
        raise ValueError("expected 0 <= start < stop")
    if stalls < 0:
        raise ValueError("stall count must be nonnegative")
    times = [t for t in frames if start <= t < stop]
    edges = [start, *times, stop]
    spans = sorted(b - a for a, b in zip(edges, edges[1:]) if b > a)
    def percentile(p):
        return spans[math.ceil(p * len(spans)) - 1] / 1000
    result = {
        "frames": len(times), "seconds": (stop - start) / 1e6,
        "fps": len(times) * 1e6 / (stop - start),
        "p95_ms": percentile(.95), "p99_ms": percentile(.99),
        "longest_ms": spans[-1] / 1000,
        "holds_over_ms": {ms: sum(t > ms * 1000 for t in spans) for ms in (50, 100, 250, 1000)},
        "seconds_in_holds_over_100ms": sum(t for t in spans if t > 100_000) / 1e6,
    }
    if stalls:
        # Reports from multiple threads can arrive out of UTC order.
        drops = sorted(compute_drops)
        gaps = ((a, b) for a, b in zip(edges, edges[1:]) if a < b)
        longest = nlargest(stalls, gaps, key=lambda gap: gap[1] - gap[0])
        result["largest_gaps"] = [
            {"start_s": a / 1e6, "stop_s": b / 1e6, "gap_ms": (b - a) / 1000,
             "compute_drop_reports": bisect_left(drops, b) - bisect_left(drops, a)}
            for a, b in longest
        ]
    return result


def report(run, metadata, start, stop, *, stalls=0, expected_output=None):
    launch = json.loads(metadata.read_text())
    if (metadata.parent / "foreground-overlap").exists() or (run / "gpu-overlap.txt").exists():
        raise ValueError("foreground GPU overlap")
    if (metadata.parent / "validation-overlap").exists():
        raise ValueError("external validation or profiling overlapped this run")
    if (run / "exit-code").read_text().strip() != "124":
        raise ValueError("run did not finish its scheduled timeout")
    if launch.get("empty_cache_directories") != dict.fromkeys(("cache", "vkd3dcache", "mesa", "xdg", "dxvk"), 0):
        raise ValueError("expected five empty cache directories at launch")
    if launch.get("story_slots") != 0:
        raise ValueError("expected a new story")
    launched = datetime.fromisoformat(launch["start_utc"])
    ended = datetime.fromisoformat(launch["end_utc"])
    duration = (ended - launched) // MICROSECOND
    if not 0 <= start < stop <= min(duration, launch["timeout"] * 1_000_000):
        raise ValueError("window outside the timed observation")
    drops = [] if stalls else None
    with (run / "run.log").open(encoding="utf-8", errors="replace") as log:
        frames = accepted_frames(log, launched, drops, expected_output=expected_output)
    if frames[-1] > duration:
        raise ValueError("frame trace extends beyond launcher metadata")
    result = {"first_present_seconds": frames[0] / 1e6, **window(frames, start, stop, stalls=stalls, compute_drops=drops)}
    if expected_output is not None:
        result["host_output"] = f"{expected_output[0]}x{expected_output[1]}"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory containing run.log and exit-code")
    parser.add_argument("metadata", type=Path, help="launch.json from the cold run")
    parser.add_argument("--start", type=int, default=0, help="seconds after launcher start")
    parser.add_argument("--stop", type=int, default=300, help="seconds after launcher start")
    parser.add_argument("--stalls", type=int, default=0, help="list the N longest gaps and compute-drop notices in each")
    parser.add_argument("--expect-output", type=output_size, metavar="WIDTHxHEIGHT",
                        help="require this host swap-chain size throughout the run")
    args = parser.parse_args()
    try:
        result = report(args.run, args.metadata, args.start * 1_000_000, args.stop * 1_000_000, stalls=args.stalls,
                        expected_output=args.expect_output)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))
