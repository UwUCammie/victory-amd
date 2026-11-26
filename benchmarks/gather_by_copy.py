"""Compare accepted frames inside the 20-second phases of VICTORY_GATHER_BY_COPY=alt."""
import argparse
from bisect import bisect_right
from datetime import datetime
import re

from first_room import ANSI, INTERVAL, TIMESTAMP


PHASE = re.compile(r"\(VICTORY_GATHER_BY_COPY=alt\): (ON|off)\b")


def phase_totals(lines, start, stop, settle):
    origin = None
    markers = []
    samples = []
    for raw in lines:
        line = ANSI.sub("", raw)
        stamp = TIMESTAMP.search(line)
        if stamp is None:
            continue
        now = datetime.fromisoformat(stamp[0].replace("Z", "+00:00"))
        if origin is None:
            origin = now
        t = (now - origin).total_seconds()
        phase = PHASE.search(line)
        if phase:
            markers.append((t, phase[1]))
        interval = INTERVAL.search(line)
        if interval:
            count, micros, draws = map(int, interval.groups())
            begin = t - micros / 1e6
            if begin >= start and t <= stop:
                samples.append((begin, t, count, micros, draws))

    # A recorder thread can write a switch line after the present thread's line.
    markers.sort()
    times = [t for t, _ in markers]
    totals = {"off": [0, 0, 0], "ON": [0, 0, 0]}
    for begin, end, frames, micros, draws in samples:
        index = bisect_right(times, begin) - 1
        if index < 0 or index != bisect_right(times, end) - 1:
            continue
        t, mode = markers[index]
        if begin < t + settle:
            continue
        row = totals[mode]
        row[0] += frames
        row[1] += micros
        row[2] += draws
    return totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=argparse.FileType("r", encoding="utf-8", errors="replace"))
    parser.add_argument("--start", type=float, default=150)
    parser.add_argument("--stop", type=float, default=385)
    parser.add_argument("--settle", type=float, default=1, help="seconds to omit after each switch")
    args = parser.parse_args()
    if not 0 <= args.start < args.stop or args.settle < 0:
        parser.error("expected 0 <= start < stop and a nonnegative settling time")
    totals = phase_totals(args.log, args.start, args.stop, args.settle)
    if not all(frames and micros for frames, micros, _ in totals.values()):
        parser.exit(1, "Both gather modes need complete measured intervals.\n")
    for mode, (frames, micros, draws) in totals.items():
        print(f"{mode}: {frames} presents in {micros / 1e6:.2f} s, "
              f"{frames * 1e6 / micros:.2f} FPS, {draws / frames:.0f} draws/frame")
