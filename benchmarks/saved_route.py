"""Classify a saved visual test after the renderer exits, without assigning an FPS."""
import argparse
import json
import math
from pathlib import Path

from cold_boot import TRACE
from first_room import DeviceLost, SessionFailed, session_lines


def classify(lines, *, interrupted, exit_code, elapsed, target):
    if interrupted:
        return "interrupted"
    if not math.isfinite(target) or not math.isfinite(elapsed) or target <= 0 or elapsed < 0:
        raise ValueError("invalid saved-route duration")
    presented = False
    try:
        for line in session_lines(lines):
            if not presented and TRACE.search(line):
                presented = True
    except DeviceLost:
        return "device-failure"
    except SessionFailed:
        return "renderer-failure"
    if exit_code != 124 or elapsed < target or not presented:
        return "incomplete"
    return "finished"


def route_outcome(run, overlap, elapsed, target):
    if overlap.exists():
        return "interrupted"
    try:
        code = (run / "exit-code").read_text().strip()
        with (run / "run.log").open(encoding="utf-8", errors="replace") as log:
            return classify(log, interrupted=overlap.exists(), exit_code=int(code) if code.isdecimal() else None,
                            elapsed=elapsed, target=target)
    except FileNotFoundError:
        return "incomplete"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory containing run.log and exit-code")
    parser.add_argument("--elapsed", type=float, required=True, help="seconds measured by the launcher")
    parser.add_argument("--target", type=float, required=True, help="configured timeout in seconds")
    parser.add_argument("--overlap", type=Path, required=True, help="this attempt's foreground-overlap marker")
    args = parser.parse_args()
    print(json.dumps({"outcome": route_outcome(args.run, args.overlap, args.elapsed, args.target)}))
