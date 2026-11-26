"""Summarize the renderer's small landed read-backs without exporting their contents."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
import re

from first_room import TIMESTAMP, session_lines

MESSAGE = "walls trace: a read-back lands in title memory"
FIELDS = re.compile(r"\bframe=(\d+)\b.*?\bbytes=(\d+) values=\[([^\]]*)\]")


def summarize(lines, launched, start=0, stop=math.inf):
    if start < 0 or start >= stop:
        raise ValueError("expected a positive time window")
    groups = defaultdict(list)
    for line in session_lines(lines):
        if MESSAGE not in line:
            continue
        timestamp = TIMESTAMP.search(line)
        fields = FIELDS.search(line)
        if not fields or not timestamp:
            raise ValueError("incomplete landed read-back message")
        elapsed = (datetime.fromisoformat(timestamp[0]) - launched).total_seconds()
        if start <= elapsed < stop:
            frame, size, values = fields.groups()
            row = tuple(map(float, values.split(","))) if values.strip() else ()
            if int(size) // 4 != len(row):
                raise ValueError("float count differs from logged byte width")
            groups[int(size)].append((int(frame), row))
    result = {}
    for size, rows in sorted(groups.items()):
        finite = [row for _, row in rows if all(map(math.isfinite, row))]
        result[size] = {
            "records": len(rows),
            "frames": len({frame for frame, _ in rows}),
            "nonfinite_records": len(rows) - len(finite),
            "all_zero_records": sum(all(v == 0 for v in row) for row in finite),
            "distinct_finite_records": len(set(finite)),
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("metadata", type=Path, help="launcher JSON containing start_utc")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--stop", type=float, default=math.inf)
    args = parser.parse_args()
    try:
        launched = datetime.fromisoformat(json.loads(args.metadata.read_text())["start_utc"])
        with args.log.open(errors="replace") as lines:
            print(json.dumps(summarize(lines, launched, args.start, args.stop), indent=2))
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f"{error}\n")
