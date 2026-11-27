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


def verify_output(lines, expected, interface=None):
    """Verify host dimensions and, when requested, the loader's successful UI setup."""
    found = False
    applied = False
    if interface is not None:
        scene = f"{expected[0]}x{expected[1]}"
        plane = f"{interface[0]}x{interface[1]}"
        plane_value = f'value="{scene} scene, {plane} interface"'
    for line in lines:
        if interface is not None and not applied and "victory_loader::resolution: resolution: patched " in line:
            applied = 'what="settings\' output size applied"' in line and plane_value in line
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
        if MARKER in line:
            if not found:
                raise ValueError("first accepted present precedes a verified swap-chain creation")
            if interface is not None and not applied:
                raise ValueError(f"first accepted present precedes a successful {scene} scene, {plane} interface setup")
        yield line
    if not found:
        raise ValueError("no host swap-chain creation in the run")


def accepted_frames(lines, launched, compute_drops=None, *, expected_output=None, expected_interface=None):
    """Anchor the first accepted present to launcher UTC, then use its monotonic clock."""
    frames = []
    first = None
    records = session_lines(lines)
    if expected_interface is not None and expected_output is None:
        raise ValueError("specify the expected host output alongside the interface size")
    if expected_output is not None:
        records = verify_output(records, expected_output, expected_interface)
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


def window(frames, start, stop, *, stalls=0, compute_drops=(), compute_gap_ms=None):
    """Times in microseconds. A present at start counts. One at stop does not."""
    if not 0 <= start < stop:
        raise ValueError("expected 0 <= start < stop")
    if stalls < 0:
        raise ValueError("stall count must be nonnegative")
    if compute_gap_ms is not None and compute_gap_ms <= 0:
        raise ValueError("compute gap threshold must be positive")
    times = [t for t in frames if start <= t < stop]
    edges = [start, *times, stop]
    gaps = [(a, b) for a, b in zip(edges, edges[1:]) if b > a]
    spans = sorted(b - a for a, b in gaps)
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
    if stalls or compute_gap_ms is not None:
        # Reports from multiple threads can arrive out of UTC order.
        drops = sorted(compute_drops)
    if stalls:
        longest = nlargest(stalls, gaps, key=lambda gap: gap[1] - gap[0])
        result["largest_gaps"] = []
        for a, b in longest:
            first = bisect_left(drops, a)
            count = bisect_left(drops, b, lo=first) - first
            result["largest_gaps"].append({
                "start_s": a / 1e6, "stop_s": b / 1e6, "gap_ms": (b - a) / 1000,
                "compute_drop_reports": count,
                "first_compute_drop_after_gap_start_s": (drops[first] - a) / 1e6 if count else None,
            })
    if compute_gap_ms is not None:
        threshold = compute_gap_ms * 1000
        long_gaps = [(a, b) for a, b in gaps if b - a >= threshold]
        result["long_gap_compute_drops"] = {
            "threshold_ms": compute_gap_ms,
            "gaps": len(long_gaps),
            "gaps_with_notice": sum(bisect_left(drops, b) > bisect_left(drops, a)
                                    for a, b in long_gaps),
            "seconds_in_gaps": sum(b - a for a, b in long_gaps) / 1e6,
        }
    return result


def check_overlap(run, metadata):
    if (metadata.parent / "foreground-overlap").exists() or (run / "gpu-overlap.txt").exists():
        raise ValueError("foreground GPU overlap")
    if (metadata.parent / "validation-overlap").exists():
        raise ValueError("external validation or profiling overlapped this run")


def loaded_vkd3d_build(lines, expected):
    """Verify the build actually loaded by the process against a commit prefix."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", expected.lower()):
        raise ValueError("expected a vkd3d-proton commit prefix of 7 to 40 hex digits")
    builds = set()
    for line in lines:
        if "vkd3d-proton - build:" in line:
            match = re.search(r"vkd3d-proton - build: ([0-9a-fA-F]{7,40})(?=[+.\s]|$)", line)
            if not match:
                raise ValueError("unrecognized vkd3d-proton build line")
            builds.add(match[1].lower())
    if len(builds) != 1:
        raise ValueError("expected one distinct vkd3d-proton build in the driver log")
    build = builds.pop()
    if not build.startswith(expected.lower()):
        raise ValueError(f"loaded vkd3d-proton build {build}, expected {expected}")
    return build


def report(run, metadata, start, stop, *, stalls=0, expected_output=None, expected_interface=None,
           expected_vkd3d=None, progress=False, compute_gap_ms=None):
    launch = json.loads(metadata.read_text())
    check_overlap(run, metadata)
    live = progress and "end_utc" not in launch
    if live and (run / "exit-code").exists():
        raise ValueError("waiting for final launcher metadata")
    if not live and (run / "exit-code").read_text().strip() != "124":
        raise ValueError("run did not finish its scheduled timeout")
    if launch.get("empty_cache_directories") != dict.fromkeys(("cache", "vkd3dcache", "mesa", "xdg", "dxvk"), 0):
        raise ValueError("expected five empty cache directories at launch")
    if launch.get("story_slots") != 0:
        raise ValueError("expected a new story")
    launched = datetime.fromisoformat(launch["start_utc"])
    duration = None if live else (datetime.fromisoformat(launch["end_utc"]) - launched) // MICROSECOND
    if not 0 <= start < stop <= launch["timeout"] * 1_000_000 or (duration is not None and stop > duration):
        raise ValueError("window outside the timed observation")
    drops = [] if stalls or compute_gap_ms is not None else None
    with (run / "run.log").open(encoding="utf-8", errors="replace") as log:
        records = (line for line in log if line.endswith("\n")) if live else log
        frames = accepted_frames(records, launched, drops, expected_output=expected_output,
                                 expected_interface=expected_interface)
    if live and frames[-1] < stop:
        raise ValueError("present trace has not yet covered the requested window")
    if duration is not None and frames[-1] > duration:
        raise ValueError("frame trace extends beyond launcher metadata")
    result = {"first_present_seconds": frames[0] / 1e6,
              **window(frames, start, stop, stalls=stalls, compute_drops=drops, compute_gap_ms=compute_gap_ms)}
    if expected_vkd3d is not None:
        with (run / "vkd3d.log").open(errors="replace") as log:
            result["vkd3d_build"] = loaded_vkd3d_build(log, expected_vkd3d)
    if live:
        check_overlap(run, metadata)
        result["provisional"] = True
    if expected_output is not None:
        result["host_output"] = f"{expected_output[0]}x{expected_output[1]}"
    if expected_interface is not None:
        result["interface_plane"] = f"{expected_interface[0]}x{expected_interface[1]}"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory containing run.log and exit-code")
    parser.add_argument("metadata", type=Path, help="launch.json from the cold run")
    parser.add_argument("--start", type=int, default=0, help="seconds after launcher start")
    parser.add_argument("--stop", type=int, default=300, help="seconds after launcher start")
    parser.add_argument("--progress", action="store_true", help="allow a provisional reading after a live trace crosses --stop")
    parser.add_argument("--expect-vkd3d", metavar="COMMIT", help="verify the loaded vkd3d-proton revision from the driver log")
    parser.add_argument("--stalls", type=int, default=0, help="list the N longest gaps and compute-drop notices in each")
    parser.add_argument("--compute-gap-ms", type=int, metavar="MS",
                        help="count gaps at least this long and how many include a compute-drop notice")
    parser.add_argument("--expect-output", type=output_size, metavar="WIDTHxHEIGHT",
                        help="require this host swap-chain size throughout the run")
    parser.add_argument("--expect-interface", type=output_size, metavar="WIDTHxHEIGHT",
                        help="also require the loader to apply this separate interface plane before the first present")
    args = parser.parse_args()
    try:
        result = report(args.run, args.metadata, args.start * 1_000_000, args.stop * 1_000_000, stalls=args.stalls,
                        expected_output=args.expect_output, expected_interface=args.expect_interface,
                        expected_vkd3d=args.expect_vkd3d, progress=args.progress, compute_gap_ms=args.compute_gap_ms)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))
