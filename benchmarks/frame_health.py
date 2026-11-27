"""Summarize private per-present render-health counters without exporting rows."""

import argparse
import csv
import json
from math import isfinite
from pathlib import Path

TOTALS = (
    "draws_ok", "draws_dropped_compiling", "draws_dropped_refused",
    "compute_ok", "compute_dropped_compiling", "compute_dropped_refused",
    "rt_skipped",
)
PEAKS = ("textures_empty_or_unready", "textures_waiting_room", "vram_mb")


def summarize(path, seconds):
    if not isfinite(seconds) or seconds <= 0:
        raise ValueError("the measurement needs a positive finite duration")
    end_ms = seconds * 1000
    elapsed_ms = 0.0
    frames = 0
    frames_with_pipeline_misses = 0
    totals = dict.fromkeys(TOTALS, 0)
    peaks = dict.fromkeys(PEAKS, 0)
    with path.open(encoding="utf-8", newline="") as file:
        rows = csv.DictReader(file)
        required = {"ms", *TOTALS, *PEAKS}
        if not required.issubset(rows.fieldnames or ()):
            raise ValueError("the CSV is missing render-health columns")
        for row in rows:
            interval = float(row["ms"])
            if not isfinite(interval) or interval < 0:
                raise ValueError("invalid elapsed time in render-health CSV")
            elapsed_ms += interval
            if elapsed_ms >= end_ms:
                break
            frames += 1
            counts = {name: int(row[name]) for name in TOTALS}
            frames_with_pipeline_misses += any(value for name, value in counts.items() if "_dropped_" in name)
            for name, value in counts.items():
                totals[name] += value
            for name in PEAKS:
                peaks[name] = max(peaks[name], int(row[name]))
    if elapsed_ms < end_ms:
        raise ValueError("the CSV ends before the requested duration")
    return {
        "seconds_from_first_present": seconds,
        "rows": frames,
        "rows_with_pipeline_misses": frames_with_pipeline_misses,
        "totals": totals,
        "peaks": peaks,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="+")
    parser.add_argument("--seconds", type=float, default=270)
    args = parser.parse_args()
    try:
        print(json.dumps([summarize(path, args.seconds) for path in args.csv], indent=2))
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
