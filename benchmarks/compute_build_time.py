"""Estimate when slow compute pipeline builds began relative to the first dropped dispatch."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from statistics import median

from cold_boot import report
from compute_lag import DROPPED_SHADER
from first_room import TIMESTAMP, session_lines


HOST = re.compile(r"victory_gpu::pipeline::host: host pipeline shaders=\[compute ([0-9a-fA-F]+)\]")


def first_events(lines):
    dropped, finished = {}, {}
    for line in session_lines(lines):
        if "victory_gpu::pipeline::make: a compute dispatch was dropped:" in line:
            events, match = dropped, DROPPED_SHADER.search(line)
        else:
            events, match = finished, HOST.search(line)
        if match and (stamp := TIMESTAMP.search(line)):
            when = datetime.fromisoformat(stamp[0].replace("Z", "+00:00")).timestamp()
            key = match[1].lower()
            events[key] = min(when, events.get(key, when))
    return dropped, finished


def estimate(dropped, finished, slow, snapshot, pipeline_key):
    # Pending::new hashes the stage string, hexadecimal shader hash and empty graphics state.
    # note_time keeps the longest measured build per key. Use only positively matched durations.
    matched = dropped.keys() & finished.keys()
    after_drop, compile_ms, before_build = [], [], []
    for shader in matched:
        cost = slow.get(pipeline_key(shader))
        if cost is None or finished[shader] > snapshot - 2:
            continue
        lag = finished[shader] - dropped[shader]
        after_drop.append(lag)
        compile_ms.append(cost)
        before_build.append(lag - cost / 1000)
    return {
        "shaders_with_first_drop": len(dropped),
        "also_logged_host_completion": len(matched),
        "matched_to_slow_build_before_snapshot": len(before_build),
        "median_seconds_drop_to_host_completion": median(after_drop) if after_drop else None,
        "median_build_seconds": median(compile_ms) / 1000 if compile_ms else None,
        "median_estimated_seconds_drop_to_build_start": median(before_build) if before_build else None,
        "estimated_build_start_over_10s_after_drop": sum(delta > 10 for delta in before_build),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory containing run.log and exit-code")
    parser.add_argument("metadata", type=Path, help="launch.json adjacent to the cold cache directory")
    args = parser.parse_args()
    try:
        from blake3 import blake3
    except ImportError:
        parser.exit(1, "Install the Python blake3 package to match runtime pipeline keys.\n")
    try:
        report(args.run, args.metadata, 0, 300_000_000, expected_output=(1280, 720), expected_interface=(3840, 2160))
        cache = args.metadata.parent / "cache/pipelines/slow-pipelines.txt"
        snapshot = cache.stat().st_mtime
        launch = json.loads(args.metadata.read_text())
        if not datetime.fromisoformat(launch["start_utc"]).timestamp() <= snapshot <= datetime.fromisoformat(launch["end_utc"]).timestamp():
            raise ValueError("the slow pipeline snapshot was not written during this launch")
        slow = {key: int(ms) for key, ms in (row.split() for row in cache.read_text().splitlines())}
        with (args.run / "run.log").open(encoding="utf-8", errors="replace") as log:
            drops, done = first_events(log)
        def pipeline_key(shader):
            return blake3(("compute" + shader).encode("ascii")).hexdigest()[:32]
        print(json.dumps(estimate(drops, done, slow, snapshot, pipeline_key), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
