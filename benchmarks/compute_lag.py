"""Match first compute-drop notices to translation completions in a saved run."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from statistics import median

from first_room import TIMESTAMP, session_lines

SHADER = re.compile(r"\bhash=([0-9a-fA-F]+)\b")
DROPPED_SHADER = re.compile(r"\bshaders=([0-9a-fA-F]+)\b")
WORKER_STARTED = re.compile(r"\bworker_started=(true|false)\b")
SIZE = re.compile(r"\bsize=(\d+)\b")


def summarize(lines, early_bytes):
    """Count distinct compute shaders and report the signed lag in seconds."""
    if early_bytes < 0:
        raise ValueError("expected a nonnegative early-compute size limit")
    drops = {}
    translated = {}
    bound = {}
    sizes = {}
    worker_started = {}
    for line in session_lines(lines):
        if "victory_gpu::pipeline::make: a compute dispatch was dropped:" in line:
            table = drops
            shader = DROPPED_SHADER.search(line)
        elif 'stage="compute"' in line and "victory_gpu::pipeline: shader translated " in line:
            table = translated
            shader = SHADER.search(line)
        elif 'stage="compute"' in line and "victory_gpu::pipeline: first bind " in line:
            table = bound
            shader = SHADER.search(line)
            size = SIZE.search(line)
            if shader and size:
                sizes[shader[1].lower()] = int(size[1])
        else:
            continue
        stamp = TIMESTAMP.search(line)
        if shader and stamp:
            key = shader[1].lower()
            time = datetime.fromisoformat(stamp[0].replace("Z", "+00:00"))
            if key not in table or time < table[key]:
                table[key] = time
                if table is drops:
                    state = WORKER_STARTED.search(line)
                    worker_started[key] = state[1] if state else None

    matched = drops.keys() & translated.keys()
    lag = [(translated[key] - drops[key]).total_seconds() for key in matched]
    sized = drops.keys() & sizes.keys()
    bind_lead = [(drops[key] - bound[key]).total_seconds() for key in drops.keys() & bound.keys()]
    return {
        "distinct_shaders_with_drop_notice": len(drops),
        "worker_started_at_first_drop": sum(state == "true" for state in worker_started.values()),
        "worker_not_started_at_first_drop": sum(state == "false" for state in worker_started.values()),
        "worker_state_unreported_at_first_drop": sum(state is None for state in worker_started.values()),
        "with_first_bind_size": len(sized),
        "with_first_bind_time": len(bind_lead),
        "median_seconds_first_drop_minus_first_bind": median(bind_lead) if bind_lead else None,
        "first_drop_within_one_ms_of_first_bind": sum(0 <= seconds < 0.001 for seconds in bind_lead),
        "first_bind_ten_seconds_or_more_before_drop": sum(seconds >= 10 for seconds in bind_lead),
        "early_limit_bytes": early_bytes,
        "above_early_limit": sum(sizes[key] > early_bytes for key in sized),
        "with_translation_completion": len(matched),
        "translation_after_first_drop": sum(dt > 0 for dt in lag),
        "median_seconds_translation_minus_first_drop": median(lag) if lag else None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--early-bytes", type=int, required=True, help="early compute size limit used in the run")
    args = parser.parse_args()
    try:
        with args.log.open(encoding="utf-8", errors="replace") as log:
            print(json.dumps(summarize(log, args.early_bytes), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
