"""Count successful presents over complete reporting intervals in a fixed window."""
import argparse
import re
from datetime import datetime

TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z")
INTERVAL = re.compile(r"victory_bench: presents frames=(\d+) interval_us=(\d+) draws=(\d+)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# The renderer emits these per-frame costs immediately after its present counter.
COSTS = {
    "Submission preparation": re.compile(r"submissions prepared by a thread of ours, per frame .*?that thread worked ([\d.]+) ms"),
    "GPU queue empty": re.compile(r"the card's clock per frame: nothing of ours queued ([\d.]+) ms"),
    "Merging fetched data": re.compile(r"landing per frame .*?merging what was fetched ([\d.]+) ms"),
    "Wait for title memory reads": re.compile(r"of the waiting for the card in settles, per frame,.*?title memory read ([\d.]+)"),
    "Wait for overlapping shader writes": re.compile(r"of the waiting for the card in settles, per frame,.*?title memory changed under shader writes ([\d.]+)"),
    "Wait for the in-flight list limit": re.compile(r"of the waiting for the card in settles, per frame,.*?lists in the air ([\d.]+)"),
}


class SessionFailed(ValueError):
    pass


class DeviceLost(SessionFailed):
    pass


def session_lines(lines):
    for raw in lines:
        line = ANSI.sub("", raw)
        if "host GPU failure:" in line or "host GPU device removed after " in line:
            raise DeviceLost("The renderer reported a GPU failure during this session.")
        if re.match(r"^\s*thread '.+?'(?: \(\d+\))? panicked at\b", line):
            raise SessionFailed("A runtime thread panicked during this session.")
        if line.startswith("VIctory: unhandled exception "):
            raise SessionFailed("The runtime reported an unhandled exception during this session.")
        yield line


def summarize(lines, start, stop, costs=None):
    origin = None
    weight = 0
    frames = elapsed = draws = 0
    for line in session_lines(lines):
        timestamp = TIMESTAMP.search(line)
        if timestamp is None:
            continue
        now = datetime.fromisoformat(timestamp[0].replace("Z", "+00:00"))
        if origin is None:
            origin = now
        interval = INTERVAL.search(line)
        if interval is None:
            if costs is not None and weight:
                for label, pattern in COSTS.items():
                    match = pattern.search(line)
                    if match:
                        total, covered = costs.get(label, (0.0, 0))
                        costs[label] = total + weight * float(match[1]), covered + weight
            continue
        weight = 0
        count, micros, work = map(int, interval.groups())
        age = (now - origin).total_seconds()
        if age - micros / 1e6 >= start and age <= stop:
            weight = count
            frames += count
            elapsed += micros
            draws += work
    return frames, elapsed, draws


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=argparse.FileType("r", encoding="utf-8", errors="replace"))
    parser.add_argument("--start", type=float, default=150)
    parser.add_argument("--stop", type=float, default=225)
    parser.add_argument("--costs", action="store_true", help="show frame-weighted renderer costs reported in the same intervals")
    args = parser.parse_args()
    if not 0 <= args.start < args.stop:
        parser.error("expected 0 <= start < stop")
    try:
        costs = {} if args.costs else None
        frames, micros, draws = summarize(args.log, args.start, args.stop, costs)
    except SessionFailed as error:
        parser.exit(1, f"{error}\n")
    if not micros or not frames:
        parser.exit(1, "No complete present intervals in that window.\n")
    print(f"{frames} presents in {micros / 1e6:.2f} s, {frames * 1e6 / micros:.2f} FPS, {draws / frames:.0f} draws/frame")
    if args.costs:
        if not costs:
            print("No renderer costs reported in the selected intervals.")
        for label in COSTS:
            if label in costs:
                total, covered = costs[label]
                print(f"{label}: {total / covered:.2f} ms/frame ({covered} frames)")
