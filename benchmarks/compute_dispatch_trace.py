"""Summarize selected dispatch outcomes without publishing shader identifiers."""

from collections import Counter
import re

from cold_boot import windowed_log_lines


BEGIN = "compute dispatch trace began"
FINISH = "compute dispatch trace finished"
OUTCOMES = {
    "skipped",
    "pipeline_unavailable",
    "pipeline_mismatch",
    "bind_rejected",
    "indirect_arguments_rejected",
    "recorded",
}


def dispatch_recording_activity(lines, launched, stop, expected_shaders):
    """Count first attempts and recordings within the launcher-time window."""
    selected = set(expected_shaders)
    began = {}
    first_outcome = {}
    first_records = {}
    outcomes = Counter()
    routes = Counter()
    completed = set()
    for time, line in windowed_log_lines(lines, launched, stop, (BEGIN, FINISH)):
        match = re.search(r'\bshader=([0-9a-f]{16})\s+attempt=(\d+)\s+route="(direct|indirect)"', line)
        if match is None or match[1] not in selected or int(match[2]) == 0:
            raise ValueError("dispatch trace has an unexpected shader, attempt or route")
        shader, attempt, route = match[1], int(match[2]), match[3]
        if BEGIN in line:
            if attempt != 1 or shader in began:
                raise ValueError("dispatch trace has a duplicate or invalid first attempt")
            began[shader] = time
            continue
        result = re.search(r'\boutcome="([a-z_]+)"\s+elapsed_us=(\d+)\s+first_recorded=(true|false)\b', line)
        if result is None or result[1] not in OUTCOMES:
            raise ValueError("dispatch trace has an invalid completion")
        if (shader, attempt) in completed:
            raise ValueError("dispatch trace completed the same attempt twice")
        completed.add((shader, attempt))
        outcome, first = result[1], result[3] == "true"
        outcomes[outcome] += 1
        routes[route] += 1
        if attempt == 1:
            first_outcome[shader] = outcome
        if first:
            if outcome != "recorded" or shader in first_records:
                raise ValueError("dispatch trace has a duplicate or invalid recording")
            first_records[shader] = time

    if any(shader not in began for shader, _ in completed):
        raise ValueError("dispatch trace is missing a first attempt")
    return {
        "tracked_shaders": len(selected),
        "shaders_attempted": len(began),
        "first_attempt_outcomes": dict(sorted(Counter(first_outcome.values()).items())),
        "first_attempts_pending_at_cutoff": len(began.keys() - first_outcome.keys()),
        "shaders_recorded": len(first_records),
        "latest_first_recording_seconds": max(first_records.values()) / 1e6 if first_records else None,
        "logged_outcomes": dict(sorted(outcomes.items())),
        "logged_routes": dict(sorted(routes.items())),
    }
