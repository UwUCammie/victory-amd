"""Reproduce the Wine launcher's fast settings in the cold 720p protocol."""

import re

from cold_boot import windowed_log_lines
from first_room import session_lines

AVATAR_WINE_COMPUTE_BUDGETS = {
    "vkd3d-master-avatar-wine-440": 10000,
    "vkd3d-master-avatar-wine-440-wait500": 500,
}
AVATAR_WINE_WRITEBACK_SWITCHES = {
    "vkd3d-master-avatar-wine-440-wc-off": "0",
    "vkd3d-master-avatar-wine-440-wc-on": "1",
}
AVATAR_WINE_MODES = AVATAR_WINE_COMPUTE_BUDGETS | dict.fromkeys(AVATAR_WINE_WRITEBACK_SWITCHES, 10000)

# Source profile: avatarmanz/VIctory-7900XTX#440, b2bf3d99, play.sh and play-1080p.sh.
# Use the benchmark's scene and UI dimensions, render offline, and keep the
# 4 GiB buffer-copy budget used for the RX 7900 XT cold tests.
AVATAR_WINE_720 = {
    "VICTORY_TEXTURE_NO_WAIT": "1",
    "VICTORY_RELAY": "2",
    "VICTORY_WIDE_BACK": "1",
    "VICTORY_CARD_REHASH_RUNS": "1",
    "VICTORY_JOIN_COPIES": "1",
    "VICTORY_INDIRECT_WINDOW": "1",
    "VICTORY_RELAY_COPY": "1",
    "VICTORY_CARD_STEPS": "2",
    "VICTORY_INDIRECT_BATCH": "2",
    "VICTORY_MAP_THREADS": "1",
    "VICTORY_TITLE_PRIORITIES": "0",
    "VICTORY_CARD_AWAKE": "1",
    "VICTORY_SHOW_AFTER": "1",
    "VICTORY_D3D12_DRED": "light",
    "VICTORY_THIN": "1",
    "VICTORY_JOIN_PARTS": "8",
    "VICTORY_UPLOAD_AHEAD": "1",
    "VICTORY_PORT_CONSTANTS": "1",
    "VICTORY_PORT_DESCRIPTORS": "1",
    "VICTORY_PORT_CBV": "1",
    "VICTORY_AMBIENT": "constant:0.08",
    "VICTORY_FRAME_INTERVAL_MS": "16.667",
    "VICTORY_CARD_BUFFERS_MIN_KB": "64",
    "VICTORY_CARD_BUFFERS_MB": "4096",
    "VICTORY_JOIN_PARTS_DRAWS": "500",
    "VICTORY_OUTPUT": "1280x720",
    "VICTORY_UI_PLANE_720": "1",
    "VICTORY_UI_VIEWBOX": "0",
    "VICTORY_BVH_BUILDER": "0",
    "VICTORY_WINE_MAP": "1",
    "VICTORY_PORT_HOME": "1",
    "VICTORY_PIPELINE_WATCH": "1",
    "VICTORY_SINGLE_LATCH": "1",
    "VICTORY_CLAMP_SYNC": "1",
    "VICTORY_LIBRARY_NULL": "1",
    "VICTORY_COMPUTE_WAIT_MS": "10000",
}


def benchmark_flags(mode):
    flags = dict(AVATAR_WINE_720, VICTORY_COMPUTE_WAIT_MS=str(AVATAR_WINE_MODES[mode]))
    if mode in AVATAR_WINE_WRITEBACK_SWITCHES:
        flags.update(VICTORY_WC_STATS="1", VICTORY_WC_NO_BACK=AVATAR_WINE_WRITEBACK_SWITCHES[mode],
                     VICTORY_WC_NO_BACK_MIN_KB="64", VICTORY_WC_KEEP_STORES="0", VICTORY_WC_CENSUS="0")
    return flags


def observed_profile(lines):
    """Report active-path evidence alongside the timed result."""
    observed = {
        "frame_rate_patched_to_60": False,
        "wine_mmap": False,
        "private_graphics_pages": False,
        "compute_wait_ms": None,
    }
    for line in session_lines(lines):
        if "frame rate: the title's read of its frame rate setting patched" in line:
            observed["frame_rate_patched_to_60"] |= bool(re.search(r"\brate=60\b", line))
        elif "title pages are shown with the host's mmap" in line:
            observed["wine_mmap"] = True
        elif "the title's 32-bit graphics pages are shown as memory of their own" in line:
            observed["private_graphics_pages"] = True
        elif "compute passes wait for their host pipeline by a budget of their own" in line:
            value = re.search(r"\bmillis=(\d+)\b", line)
            if value:
                observed["compute_wait_ms"] = int(value[1])
    return observed


def compute_wait_activity(lines, launched, stop):
    """Count wait reports by outcome, including reports from concurrent threads."""
    label = "a compute pass was waited for"
    totals = {"reports": 0, "without_pipeline_result": 0, "longest_reported_wait_ms": 0}
    for _, line in windowed_log_lines(lines, launched, stop, (label,)):
        match = re.search(r"\bms=(\d+)\s+made=(true|false)\b", line)
        if match is None:
            raise ValueError("compute wait result has no duration or pipeline status")
        totals["reports"] += 1
        totals["without_pipeline_result"] += match[2] == "false"
        totals["longest_reported_wait_ms"] = max(totals["longest_reported_wait_ms"], int(match[1]))
    return totals


def writeback_activity(lines, launched, stop, enabled):
    stats = "title memory by what the title asked for (VICTORY_WC_STATS)"
    kept = "shaders' writes into write-combined title memory left on the card"
    stats_count = kept_count = positive_count = 0
    for _, line in windowed_log_lines(lines, launched, stop, (stats, kept)):
        if stats in line:
            stats_count += 1
        else:
            match = re.search(r"\bper frame: (\d+) declarations", line)
            if match is None or "under 64 KiB kept" not in line:
                raise ValueError("unexpected write-combined memory report")
            kept_count += 1
            positive_count += int(match[1]) > 0
    if not stats_count or bool(kept_count) != enabled:
        raise ValueError("write-back diagnostics do not match the requested mode")
    return {"statistics_intervals": stats_count, "kept_intervals": kept_count,
            "intervals_with_kept_declarations": positive_count}
