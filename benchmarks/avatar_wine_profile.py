"""Reproduce the Wine launcher's fast settings in the cold 720p protocol."""

import re

from first_room import session_lines

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
