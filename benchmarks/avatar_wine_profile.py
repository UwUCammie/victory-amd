"""Reproduce the Wine launcher's fast settings in the cold 720p protocol."""

import ast
import re
from statistics import median

from cold_boot import windowed_log_lines
from first_room import session_lines

AVATAR_WINE_COMPUTE_BUDGETS = {
    "vkd3d-master-avatar-wine-440": 10000,
    "vkd3d-master-avatar-wine-440-wait500": 500,
}
AVATAR_WINE_WRITEBACK_SWITCHES = {
    "vkd3d-master-avatar-wine-440-wc-off": "0",
    "vkd3d-master-avatar-wine-440-wc-on": "1",
    "vkd3d-master-avatar-wine-440-wc-bounds-off": "0",
    "vkd3d-master-avatar-wine-440-wc-bounds-on": "1",
}
AVATAR_WINE_LEGACY_FMA = "vkd3d-master-avatar-wine-440-legacy-fma-3072"
AVATAR_WINE_VALUE_USE_INDEX = "vkd3d-master-avatar-wine-440-value-use-index"
AVATAR_WINE_KEEP_TRANSLATED = "vkd3d-master-avatar-wine-440-keep-translated"
AVATAR_WINE_SINGLE_PARSE = "vkd3d-master-avatar-wine-440-single-parse"
AVATAR_WINE_BOOL_SIMPLIFY = "vkd3d-master-avatar-wine-440-bool-simplify"
AVATAR_WINE_COMPILER_CACHE = "vkd3d-master-avatar-wine-440-compiler-cache"
AVATAR_WINE_LATEST_CONTROL = "vkd3d-master-avatar-wine-440-latest-control"
AVATAR_WINE_LATEST_SHADERS = "vkd3d-master-avatar-wine-440-latest-shaders"
AVATAR_WINE_FACES = "vkd3d-master-avatar-wine-440-faces"
AVATAR_WINE_FACES_OFF = "vkd3d-master-avatar-wine-440-faces-early-off"
AVATAR_WINE_FACES_EARLY = "vkd3d-master-avatar-wine-440-faces-early"
AVATAR_WINE_FACES_2S = "vkd3d-master-avatar-wine-440-faces-early-2s"
AVATAR_WINE_FACES_HALF_FIX = "vkd3d-master-avatar-wine-440-faces-listed-half"
AVATAR_WINE_PIPELINE_INPUTS = "vkd3d-master-avatar-wine-440-pipeline-inputs"
AVATAR_WINE_CARD_TOUCHED = {
    "vkd3d-master-avatar-wine-440-card-touched-off": "0",
    "vkd3d-master-avatar-wine-440-card-touched-on": "1",
}
AVATAR_WINE_OBSERVERS_OFF = "vkd3d-master-avatar-wine-440-observers-off"
AVATAR_WINE_OBSERVERS_ON = "vkd3d-master-avatar-wine-440-observers-on"
AVATAR_WINE_MERGED_COLD = "vkd3d-master-avatar-wine-440-merged-cold"
AVATAR_WINE_WRITE_WATCH_INDEX = "vkd3d-master-avatar-wine-440-write-watch-index"
AVATAR_WINE_RECORDED_COMPUTE = {
    "vkd3d-master-avatar-wine-440-recorded-compute-off": "0",
    "vkd3d-master-avatar-wine-440-recorded-compute-on": "1",
}
AVATAR_WINE_RECORDED_SCREEN = {
    "vkd3d-master-avatar-wine-440-recorded-screen-off": "0",
    "vkd3d-master-avatar-wine-440-recorded-screen-on": "1",
}
AVATAR_WINE_SCREEN_WAITER_SCORES = {
    "vkd3d-master-avatar-wine-440-merged-screen-waiter-off": "0",
    "vkd3d-master-avatar-wine-440-merged-screen-waiter-on": "screen",
}
AVATAR_WINE_WRITE_WATCH_GAPS = {
    "vkd3d-master-avatar-wine-440-write-watch-8m": 8192,
    "vkd3d-master-avatar-wine-440-write-watch-1m": 1024,
}
AVATAR_WINE_CAPTURE_OBSERVERS = {
    AVATAR_WINE_OBSERVERS_OFF: False, AVATAR_WINE_OBSERVERS_ON: True, AVATAR_WINE_MERGED_COLD: False,
    AVATAR_WINE_WRITE_WATCH_INDEX: False,
    **dict.fromkeys(AVATAR_WINE_RECORDED_COMPUTE, False),
    **dict.fromkeys(AVATAR_WINE_RECORDED_SCREEN, False),
    **dict.fromkeys(AVATAR_WINE_SCREEN_WAITER_SCORES, False),
    **dict.fromkeys(AVATAR_WINE_WRITE_WATCH_GAPS, False),
}
AVATAR_WINE_FACE_WORKER_COUNTS = {
    "vkd3d-master-avatar-wine-440-faces-workers6": 6,
    "vkd3d-master-avatar-wine-440-faces-workers14": 14,
}
AVATAR_WINE_FACE_TRACE = "vkd3d-master-avatar-wine-440-face-dispatch-trace"
AVATAR_WINE_FACE_TRACE_EARLY = "vkd3d-master-avatar-wine-440-face-dispatch-trace-early"
AVATAR_WINE_FACE_TRACE_LIMITS = {
    AVATAR_WINE_FACE_TRACE: 0,
    AVATAR_WINE_FACE_TRACE_EARLY: 3072,
}
FACE_TRACE_SECONDS = 95
FACE_TRACE_CUTOFF = 88_000_000
AVATAR_WINE_FACE_EARLY_LIMITS = {
    AVATAR_WINE_FACES_OFF: 0,
    AVATAR_WINE_FACES_EARLY: 3072,
    AVATAR_WINE_FACES_2S: 3072,
    AVATAR_WINE_FACES_HALF_FIX: 3072,
    AVATAR_WINE_PIPELINE_INPUTS: 3072,
    **dict.fromkeys(AVATAR_WINE_CARD_TOUCHED, 3072),
    **dict.fromkeys(AVATAR_WINE_CAPTURE_OBSERVERS, 3072),
    **dict.fromkeys(AVATAR_WINE_FACE_WORKER_COUNTS, 3072),
}
AVATAR_WINE_EARLY_LIMITS = {
    "vkd3d-master-avatar-wine-440-early-off": 0,
    "vkd3d-master-avatar-wine-440-early-1k": 1024,
    "vkd3d-master-avatar-wine-440-early-2560": 2560,
    "vkd3d-master-avatar-wine-440-early-2560-wait2000": 2560,
    "vkd3d-master-avatar-wine-440-early-3072-wait2000": 3072,
    AVATAR_WINE_LEGACY_FMA: 3072,
    **AVATAR_WINE_FACE_EARLY_LIMITS,
}
AVATAR_WINE_NOTIFY_SWITCHES = {
    "vkd3d-master-avatar-wine-440-notify-global": "0",
    "vkd3d-master-avatar-wine-440-notify-local": "1",
}
AVATAR_WINE_SCREEN_LIMITS = {
    "vkd3d-master-avatar-wine-440-screen-early-off": 0,
    "vkd3d-master-avatar-wine-440-screen-early-6k": 6144,
}
AVATAR_WINE_SCREEN_WORKERS = {
    "vkd3d-master-avatar-wine-440-screen-worker-shared": "0",
    "vkd3d-master-avatar-wine-440-screen-worker-reserved": "1",
}
AVATAR_WINE_CONSTRUCTOR_POOLS = {
    "vkd3d-master-avatar-wine-440-list-pool-off": "0",
    "vkd3d-master-avatar-wine-440-list-pool-on": "1",
}
AVATAR_WINE_WAITER_SWITCHES = {
    "vkd3d-master-avatar-wine-440-waiters-first-off": "0",
    "vkd3d-master-avatar-wine-440-waiters-first-on": "1",
}
AVATAR_WINE_QUEUE_TIMING = "vkd3d-master-avatar-wine-440-queue-timing"
AVATAR_WINE_QUEUE_TIMINGS = {
    AVATAR_WINE_QUEUE_TIMING: "0",
    "vkd3d-master-avatar-wine-440-queue-timing-on": "1",
}
AVATAR_WINE_STAGE_CPU_PROFILE = "vkd3d-master-avatar-wine-440-stage-timing-cpu"
AVATAR_WINE_STAGE_INDEX_PROFILE = "vkd3d-master-avatar-wine-440-stage-timing-index"
AVATAR_WINE_STAGE_CPU_PROFILES = (AVATAR_WINE_STAGE_CPU_PROFILE, AVATAR_WINE_STAGE_INDEX_PROFILE)
AVATAR_WINE_SCREEN_QUEUE_TRACE = "vkd3d-master-avatar-wine-440-faces-screen-queue"
AVATAR_WINE_SCREEN_QUEUE_10S = "vkd3d-master-avatar-wine-440-faces-screen-queue-10s"
AVATAR_WINE_SCREEN_QUEUE_PRIORITY = "vkd3d-master-avatar-wine-440-faces-screen-queue-10s-on"
AVATAR_WINE_SCREEN_WAIT_BOUNDARIES = "vkd3d-master-avatar-wine-440-faces-screen-wait-boundaries"
AVATAR_WINE_SCREEN_WAITER_DIAGNOSTICS = {
    "vkd3d-master-avatar-wine-440-screen-waiter-off": "0",
    "vkd3d-master-avatar-wine-440-screen-waiter-on": "screen",
}
AVATAR_WINE_SCREEN_QUEUE_TRACES = (
    AVATAR_WINE_SCREEN_QUEUE_TRACE, AVATAR_WINE_SCREEN_QUEUE_10S, AVATAR_WINE_SCREEN_QUEUE_PRIORITY,
    AVATAR_WINE_SCREEN_WAIT_BOUNDARIES, *AVATAR_WINE_SCREEN_WAITER_DIAGNOSTICS,
)
AVATAR_WINE_STAGE_TIMINGS = {
    "vkd3d-master-avatar-wine-440-stage-timing-off": "0",
    "vkd3d-master-avatar-wine-440-stage-timing-on": "1",
    **dict.fromkeys(AVATAR_WINE_STAGE_CPU_PROFILES, "0"),
    AVATAR_WINE_SCREEN_QUEUE_TRACE: "0",
    AVATAR_WINE_SCREEN_QUEUE_10S: "0",
    AVATAR_WINE_SCREEN_QUEUE_PRIORITY: "1",
    AVATAR_WINE_SCREEN_WAIT_BOUNDARIES: "0",
    **AVATAR_WINE_SCREEN_WAITER_DIAGNOSTICS,
}
STAGE_TRACE_SECONDS = 82
STAGE_TRACE_CUTOFF = 75_000_000
AVATAR_WINE_MODES = AVATAR_WINE_COMPUTE_BUDGETS | dict.fromkeys(
    (*AVATAR_WINE_WRITEBACK_SWITCHES, *AVATAR_WINE_EARLY_LIMITS, *AVATAR_WINE_NOTIFY_SWITCHES,
     AVATAR_WINE_VALUE_USE_INDEX, AVATAR_WINE_KEEP_TRANSLATED, AVATAR_WINE_SINGLE_PARSE,
     AVATAR_WINE_COMPILER_CACHE, AVATAR_WINE_BOOL_SIMPLIFY, AVATAR_WINE_LATEST_CONTROL,
     AVATAR_WINE_LATEST_SHADERS, AVATAR_WINE_FACES, *AVATAR_WINE_FACE_TRACE_LIMITS, *AVATAR_WINE_CONSTRUCTOR_POOLS,
     *AVATAR_WINE_WAITER_SWITCHES, *AVATAR_WINE_QUEUE_TIMINGS, *AVATAR_WINE_STAGE_TIMINGS), 10000
) | dict.fromkeys((*AVATAR_WINE_SCREEN_LIMITS, *AVATAR_WINE_SCREEN_WORKERS, "vkd3d-master-avatar-wine-440-early-2560-wait2000",
                   "vkd3d-master-avatar-wine-440-early-3072-wait2000", AVATAR_WINE_LEGACY_FMA,
                   AVATAR_WINE_FACES_2S, AVATAR_WINE_SCREEN_QUEUE_TRACE), 2000)

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
    if mode in AVATAR_WINE_CARD_TOUCHED or mode in AVATAR_WINE_CAPTURE_OBSERVERS:
        flags.update(VICTORY_CARD_TOUCHED=AVATAR_WINE_CARD_TOUCHED.get(mode, "0"),
                     VICTORY_WC_NO_BACK="0", VICTORY_WC_KEEP_STORES="0")
    if mode in AVATAR_WINE_EARLY_LIMITS:
        flags["VICTORY_EARLY_COMPUTE_MAX_BYTES"] = str(AVATAR_WINE_EARLY_LIMITS[mode])
    if mode in AVATAR_WINE_NOTIFY_SWITCHES:
        flags.update(VICTORY_EARLY_COMPUTE_MAX_BYTES="2560",
                     VICTORY_BENCH_LOCAL_PIPELINE_NOTIFY=AVATAR_WINE_NOTIFY_SWITCHES[mode])
    if mode in AVATAR_WINE_SCREEN_LIMITS:
        flags.update(VICTORY_EARLY_COMPUTE_MAX_BYTES="2560", VICTORY_SCREEN_WAIT_MS="10000",
                     VICTORY_EARLY_SCREEN_MAX_BYTES=str(AVATAR_WINE_SCREEN_LIMITS[mode]))
    if mode in AVATAR_WINE_SCREEN_WORKERS:
        flags.update(VICTORY_EARLY_COMPUTE_MAX_BYTES="2560", VICTORY_SCREEN_WAIT_MS="10000",
                     VICTORY_EARLY_SCREEN_MAX_BYTES="0", VICTORY_RESERVE_SCREEN_WORKER=AVATAR_WINE_SCREEN_WORKERS[mode])
    if mode in AVATAR_WINE_CONSTRUCTOR_POOLS:
        flags.update(VICTORY_LIST_POOL="1", VICTORY_LIST_CREATE_POOL=AVATAR_WINE_CONSTRUCTOR_POOLS[mode])
    if mode in AVATAR_WINE_WAITER_SWITCHES:
        flags.update(VICTORY_PIPELINE_WAITERS_FIRST=AVATAR_WINE_WAITER_SWITCHES[mode], VICTORY_PIPELINE_QUEUE_TIMING="0")
    if mode in AVATAR_WINE_SCREEN_WAITER_SCORES:
        flags.update(VICTORY_PIPELINE_WAITERS_FIRST=AVATAR_WINE_SCREEN_WAITER_SCORES[mode],
                     VICTORY_PIPELINE_QUEUE_TIMING="0", VICTORY_PIPELINE_STAGE_TIMING="0")
    if mode in AVATAR_WINE_QUEUE_TIMINGS:
        flags.update(VICTORY_PIPELINE_WAITERS_FIRST=AVATAR_WINE_QUEUE_TIMINGS[mode], VICTORY_PIPELINE_QUEUE_TIMING="1")
    if mode in AVATAR_WINE_STAGE_TIMINGS:
        flags.update(VICTORY_PIPELINE_WAITERS_FIRST=AVATAR_WINE_STAGE_TIMINGS[mode],
                     VICTORY_PIPELINE_QUEUE_TIMING="1", VICTORY_PIPELINE_STAGE_TIMING="1")
    if mode == AVATAR_WINE_FACES or mode in AVATAR_WINE_FACE_EARLY_LIMITS or mode in AVATAR_WINE_FACE_TRACE_LIMITS:
        flags["VICTORY_RAW_TYPED_LOADS"] = "1"
    if mode in AVATAR_WINE_SCREEN_QUEUE_TRACES:
        flags.update(VICTORY_RAW_TYPED_LOADS="1", VICTORY_EARLY_COMPUTE_MAX_BYTES="3072")
    if mode in AVATAR_WINE_FACE_TRACE_LIMITS:
        flags["VICTORY_EARLY_COMPUTE_MAX_BYTES"] = str(AVATAR_WINE_FACE_TRACE_LIMITS[mode])
    if mode in AVATAR_WINE_FACE_WORKER_COUNTS:
        flags["VICTORY_PIPELINE_WORKERS"] = str(AVATAR_WINE_FACE_WORKER_COUNTS[mode])
    if mode in AVATAR_WINE_WRITE_WATCH_GAPS:
        flags["VICTORY_AHEAD_GAP_KIB"] = str(AVATAR_WINE_WRITE_WATCH_GAPS[mode])
    if mode in AVATAR_WINE_RECORDED_COMPUTE:
        flags.update(VICTORY_EARLY_RECORDED_COMPUTE=AVATAR_WINE_RECORDED_COMPUTE[mode],
                     VICTORY_RECORDED_COMPUTE_TRACE="1")
    if mode in AVATAR_WINE_RECORDED_SCREEN:
        flags.update(VICTORY_EARLY_RECORDED_SCREEN=AVATAR_WINE_RECORDED_SCREEN[mode],
                     VICTORY_RECORDED_SCREEN_TRACE="1", VICTORY_EARLY_RECORDED_COMPUTE="0",
                     VICTORY_RECORDED_COMPUTE_TRACE="0")
    return flags


def verify_capture_observers(launch, capture_dir, enabled, *, complete=False):
    """Check which observer processes started and whether they wrote captures."""
    expected = ["stills", "clip"] if enabled else []
    flags = launch.get("runtime_flags", {})
    if launch.get("capture_observers") != expected or launch.get("runtime_capture") != "0":
        raise ValueError("capture observer launch did not match the requested mode")
    if any(name.startswith("VICTORY_CAPTURE") for name in flags):
        raise ValueError("runtime capture must be unset in both modes")
    stills = any(path.stat().st_size > 0 for path in capture_dir.glob("private-*.png"))
    clip_path = capture_dir / "private-dialogue.mkv"
    clip = clip_path.is_file() and clip_path.stat().st_size > 0
    if (stills, clip) != (enabled, enabled):
        raise ValueError("capture observer outputs did not match the requested mode")
    if complete and enabled and launch.get("capture_observer_exit_codes", {}).get("clip") != 0:
        raise ValueError("clip recorder did not complete its requested window")


def verify_card_dirty_scan(lines, launched, stop, enabled):
    """Confirm which dirty scan the running build selected."""
    label = "card copy dirty scan mode"
    modes = [line.rsplit(label, 1)[1].strip()
             for _, line in windowed_log_lines(lines, launched, stop, (label,))]
    if modes != [f"enabled={str(enabled).lower()}"]:
        raise ValueError("runtime card copy dirty scan mode did not match")


def verify_write_watch_gap(lines, launched, stop, kib):
    label = "write-watch join gap"
    modes = [line.rsplit(label, 1)[1].strip()
             for _, line in windowed_log_lines(lines, launched, stop, (label,))]
    if modes != [f"kib={kib}"]:
        raise ValueError("runtime write-watch join gap did not match")


def write_watch_index_activity(lines, launched, stop):
    label = "indexed write-watch ranges"
    for elapsed, line in windowed_log_lines(lines, launched, stop, (label,)):
        match = re.search(r"requests=(\d+)\s+remaining=(\d+)", line)
        if match is None:
            raise ValueError("malformed write-watch range index marker")
        return {"first_us": elapsed, "requests": int(match[1]), "remaining": int(match[2])}
    return None


def recorded_compute_activity(lines, launched, stop, enabled):
    """Measure the first recorded dispatch to first replay use of each pipeline."""
    return _recorded_pipeline_activity(lines, launched, stop, enabled, "compute")


def recorded_screen_activity(lines, launched, stop, enabled):
    """Measure screen pipeline readiness, including a route with no direct screen draws."""
    return _recorded_pipeline_activity(lines, launched, stop, enabled, "screen")


def _recorded_pipeline_activity(lines, launched, stop, enabled, kind):
    settings = f"recorded {kind} pipeline lookahead"
    queued = f"first recorded {kind} pipeline queued before replay"
    replay = f"recorded {kind} pipeline reached replay"
    mode = []
    leads = []
    ready = 0
    first_queued = None
    for elapsed, line in windowed_log_lines(lines, launched, stop, (settings, queued, replay)):
        if settings in line:
            mode.append(line.rsplit(settings, 1)[1].strip())
        elif queued in line and first_queued is None:
            first_queued = elapsed
        elif replay in line:
            match = re.search(r"us=(\d+)\s+ready=(true|false)", line)
            if match is None:
                raise ValueError(f"malformed recorded {kind} replay marker")
            leads.append(int(match[1]))
            ready += match[2] == "true"
    if mode != [f"enabled={str(enabled).lower()} trace=true"] or (not enabled and first_queued is not None):
        raise ValueError(f"recorded {kind} pipeline setting did not match")
    if not leads and kind == "compute":
        raise ValueError("no recorded compute pipelines reached replay")
    return {
        "count": len(leads),
        "ready_at_first_replay": ready,
        "lead_median_us": median(leads) if leads else None,
        "lead_p95_us": sorted(leads)[(95 * len(leads) + 99) // 100 - 1] if leads else None,
        "lead_max_us": max(leads, default=None),
        "lead_over_100ms": sum(us > 100_000 for us in leads),
        "first_queued_us": first_queued,
    }


def verify_pipeline_workers(lines, launched, stop, expected):
    """Confirm the configured count of general pipeline workers."""
    workers = set()
    for _, line in windowed_log_lines(lines, launched, stop, ("pipeline workers",)):
        match = re.search(r"\bpipeline workers\s+workers=(\d+)\b", line)
        if match:
            workers.add(int(match[1]))
    if workers != {expected}:
        raise ValueError("general pipeline worker count did not match")


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


def early_compute_activity(lines, launched, stop, expected_limit):
    return _early_pipeline_activity(lines, launched, stop, expected_limit, "compute")


def early_screen_activity(lines, launched, stop, expected_limit):
    return _early_pipeline_activity(lines, launched, stop, expected_limit, "screen")


def _early_pipeline_activity(lines, launched, stop, expected_limit, kind):
    limit_label = f"cold {kind} pipeline byte limit"
    start_label = f"first small {kind} pipeline started at creation"
    limits = set()
    first_started = None
    for at, line in windowed_log_lines(lines, launched, stop, (limit_label, start_label)):
        if limit_label in line:
            match = re.search(r"\bbytes=(\d+)\b", line)
            if match is None:
                raise ValueError(f"{kind} size limit has no byte value")
            limits.add(int(match[1]))
        else:
            first_started = at
    if limits != {expected_limit} or (first_started is not None) != bool(expected_limit):
        raise ValueError(f"early {kind} diagnostics do not match the requested mode")
    return {"limit_bytes": expected_limit,
            f"first_early_{kind}_seconds": None if first_started is None else first_started / 1e6}


def screen_worker_activity(lines, launched, stop, expected):
    """Check that the requested permanent reserve was created and used."""
    label = "dedicated screen pipeline worker"
    claim = f"{label} claimed its first pass"
    config = []
    claims = []
    for stamp, line in windowed_log_lines(lines, launched, stop, (label,)):
        if claim in line:
            claims.append(stamp)
        else:
            match = re.search(r"\breserved=(true|false)\b", line)
            if match is None:
                raise ValueError("screen worker configuration lacks a reservation flag")
            config.append(match[1] == "true")
    if config != [expected] or len(claims) != int(expected):
        raise ValueError("screen worker configuration or first claim does not match the requested mode")
    return {"reserved": expected, "first_claim_seconds": claims[0] / 1e6 if claims else None}


_WAIT_LABELS = {"a pass over the screen was waited for": "screen", "a compute pass was waited for": "compute"}


def _pipeline_wait_reports(lines, launched, stop):
    for end, line in windowed_log_lines(lines, launched, stop, tuple(_WAIT_LABELS)):
        match = re.search(r"\bms=(\d+)\s+made=(true|false)\b", line)
        if match is None:
            raise ValueError("pipeline wait result has no duration or pipeline status")
        kind = next(kind for label, kind in _WAIT_LABELS.items() if label in line)
        yield kind, end - int(match[1]) * 1000, end, line


def _pipeline_wait_spans(lines, launched, stop):
    spans = {"screen": [], "compute": []}
    for kind, start, end, _ in _pipeline_wait_reports(lines, launched, stop):
        spans[kind].append((start, end))
    return {kind: sorted(waits) for kind, waits in spans.items()}


def _wait_overlap(waits, start, end):
    covered, through = 0, start
    for lo, hi in waits:
        if lo >= end:
            break
        lo, hi = max(lo, through), min(hi, end)
        if hi > lo:
            covered += hi - lo
            through = hi
    return covered


def screen_wait_coverage(lines, launched, stop, frames):
    """Intersect completed wait reports with the five longest complete gaps."""
    spans = _pipeline_wait_spans(lines, launched, stop)
    gaps = ((a, b) for a, b in zip(frames, frames[1:]) if b <= stop and b > a)
    return [{"start_seconds": a / 1e6, "gap_ms": (b - a) / 1000,
             **{f"{kind}_overlap_ms": _wait_overlap(waits, a, b) / 1000 for kind, waits in spans.items()}}
            for a, b in sorted(gaps, key=lambda gap: gap[1] - gap[0], reverse=True)[:5]]


def pipeline_wait_gap_totals(lines, launched, stop, frames):
    """Report how many long-gap seconds overlap completed pipeline waits."""
    spans = _pipeline_wait_spans(lines, launched, stop)
    spans["either"] = sorted(spans["screen"] + spans["compute"])
    edges = [0, *(stamp for stamp in frames if 0 <= stamp < stop), stop]
    gaps = [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 100_000]
    return {"long_gap_seconds": sum(b - a for a, b in gaps) / 1e6,
            **{f"{kind}_overlap_seconds": sum(_wait_overlap(waits, a, b) for a, b in gaps) / 1e6
               for kind, waits in spans.items()}}


def _complete_long_gaps(frames, stop):
    return [(a, b) for a, b in zip(frames, frames[1:]) if 0 <= a < b <= stop and b - a >= 1_000_000]


def pipeline_wait_group_coverage(lines, launched, stop, frames):
    """Aggregate wait groups in complete present gaps lasting at least a second.

    A group shares both its shader list and its compute/screen wait class.
    Several pipeline configurations can use the same shader list.
    """
    groups = {}
    for kind, start, end, line in _pipeline_wait_reports(lines, launched, stop):
        match = re.search(r"\bshaders=(\[[^\]]+\])", line)
        if match is None:
            raise ValueError("pipeline wait result has no shader list")
        groups.setdefault((kind, match[1]), []).append((start, end))

    group_spans = [sorted(waits) for waits in groups.values()]
    all_spans = sorted(span for waits in group_spans for span in waits)
    gaps = _complete_long_gaps(frames, stop)
    largest_per_gap = [max((_wait_overlap(waits, a, b) for waits in group_spans), default=0) for a, b in gaps]
    return {
        "gaps_at_least_one_second": len(gaps),
        "gap_seconds": sum(b - a for a, b in gaps) / 1e6,
        "any_wait_overlap_seconds": sum(_wait_overlap(all_spans, a, b) for a, b in gaps) / 1e6,
        "largest_group_overlap_seconds": sum(largest_per_gap) / 1e6,
        "gaps_with_one_group_covering_at_least_80_percent": sum(
            5 * overlap >= 4 * (b - a) for (a, b), overlap in zip(gaps, largest_per_gap)
        ),
    }


def pipeline_wait_translation_coverage(lines, launched, stop, frames):
    """Measure long-gap wait overlap before and after the last shader translation.

    A missing marker makes a wait unclassified. Time covered by separate
    waiters can appear in more than one column.
    """
    translated = {}
    wait_lines = []
    for time, line in windowed_log_lines(lines, launched, stop, ("shader translated", *_WAIT_LABELS)):
        if "shader translated" in line:
            shader = re.search(r'\bstage="([^"]+)"\s+hash=([0-9a-f]{16})\b', line)
            if shader is None:
                raise ValueError("shader translation result has no stage or hash")
            translated.setdefault(shader.groups(), time)
        else:
            wait_lines.append(line)
    spans = {"translation_pending": [], "translation_logged": [], "translation_unknown": []}
    for _, start, end, line in _pipeline_wait_reports(wait_lines, launched, stop):
        shaders = re.search(r"\bshaders=\[([^\]]+)\]", line)
        if shaders is None:
            raise ValueError("pipeline wait result has no shader list")
        times = [translated.get(tuple(shader.split())) for shader in shaders[1].split(", ")]
        if any(time is None for time in times):
            spans["translation_unknown"].append((start, end))
            continue
        compiled = max(times)
        if compiled > start:
            spans["translation_pending"].append((start, min(end, compiled)))
        if compiled < end:
            spans["translation_logged"].append((max(start, compiled), end))
    gaps = _complete_long_gaps(frames, stop)
    for waits in spans.values():
        waits.sort()
    return {
        f"{kind}_overlap_seconds": sum(_wait_overlap(waits, a, b) for a, b in gaps) / 1e6
        for kind, waits in spans.items()
    }


def verify_waiter_priority(lines, launched, stop, expected):
    label = "pipeline priority for active waiters"
    seen = set()
    for _, line in windowed_log_lines(lines, launched, stop, (label,)):
        value = re.search(r"\benabled=(true|false)\b", line)
        if value is None:
            raise ValueError("pipeline waiter priority log has no setting")
        seen.add(value[1] == "true")
    if seen != {expected}:
        raise ValueError("pipeline waiter priority does not match the requested mode")


def verify_screen_waiter_priority(lines, launched, stop, enabled):
    label = "pipeline priority for active waiters"
    modes = [line.rsplit(label, 1)[1].strip()
             for _, line in windowed_log_lines(lines, launched, stop, (label,))]
    if modes != [f"enabled=false screen_only={str(enabled).lower()}"]:
        raise ValueError("screen-only pipeline waiter priority did not match")


def queue_claim_activity(lines, launched, stop, frames, *, screen=False):
    """Measure first-request-to-worker delay and its overlap with pipeline waits.

    Screen waits use the pipeline key because their shader lists can be shared.
    A reported wait must match a single recorded claim to contribute overlap.
    """
    claims = {}
    waits = []
    label = "a requested pipeline reached a worker"
    wait_label = "a pass over the screen was waited for" if screen else "a compute pass was waited for"
    kind = "screen" if screen else "compute"
    identity = re.compile(r'\bkey="([0-9a-f]+)"' if screen else r"\bshaders=(\[[^\]]*\])")
    delays = []
    for at, line in windowed_log_lines(lines, launched, stop, (label, wait_label)):
        if label not in line:
            waits.append(line)
            continue
        duration = re.search(r"\bus=(\d+)\b", line)
        key = identity.search(line)
        if duration is None or key is None:
            raise ValueError("queue claim has no duration or pipeline identity")
        delay = int(duration[1])
        delays.append(delay)
        claims.setdefault(key[1], []).append((at - delay, at))

    queued = []
    matched = 0
    for _, start, end, line in _pipeline_wait_reports(waits, launched, stop):
        key = identity.search(line)
        if key is None:
            raise ValueError("pipeline wait has no pipeline identity")
        claim = claims.get(key[1])
        if claim is not None and len(claim) == 1:
            requested, picked = claim[0]
            lo, hi = max(start, requested), min(end, picked)
            if lo < hi:
                queued.append((lo, hi))
            matched += 1
    queued.sort()
    return {
        "recorded_claims": len(delays),
        "claims_after_100ms": sum(delay > 100_000 for delay in delays),
        "longest_claim_delay_ms": max(delays, default=0) / 1000,
        f"{kind}_wait_reports": len(waits),
        f"matched_{kind}_wait_reports": matched,
        f"queued_{kind}_overlap_seconds": sum(_wait_overlap(queued, a, b) for a, b in _complete_long_gaps(frames, stop)) / 1e6,
    }


def screen_wait_progress(lines, launched, stop, frames):
    """Include waits that had started and were still open at the trace cutoff."""
    began = "screen pipeline wait started"
    ended = "screen pipeline wait ended"
    active = {}
    seen = set()
    completed = 0
    for at, line in windowed_log_lines(lines, launched, stop, (began, ended)):
        match = re.search(r"\bid=(\d+)\b", line)
        if match is None:
            raise ValueError("screen wait boundary has no ID")
        wait = int(match[1])
        if began in line:
            if wait in seen:
                raise ValueError("screen wait started twice")
            seen.add(wait)
            active[wait] = at
        else:
            start = active.pop(wait, None)
            if start is None or at < start:
                raise ValueError("screen wait ended without its start")
            completed += 1
    still_waiting = sorted((start, stop) for start in active.values())
    return {
        "started": len(seen),
        "ended": completed,
        "open_at_cutoff": len(active),
        "longest_open_wait_seconds": (stop - min(active.values())) / 1e6 if active else 0,
        "open_wait_gap_overlap_seconds": sum(_wait_overlap(still_waiting, left, right)
                                             for left, right in _complete_long_gaps(frames, stop)) / 1e6,
    }


def pipeline_stage_activity(lines, launched, stop, frames):
    """Measure how host pipeline phases overlap compute waits and long gaps."""
    label = "host pipeline timing"
    compute = "a compute pass was waited for"
    stages = ("bindings", "root_signature", "description", "library", "library_load_guards",
              "driver_load", "driver_create", "library_store_guards", "driver_store", "after_driver")
    traces = {}
    waits = []
    for end, line in windowed_log_lines(lines, launched, stop, (label, compute)):
        if label not in line:
            waits.append(line)
            continue
        fields = re.search(r"\bus=(\d+)\s+shaders=(\[[^\]]*\])\s+phases=(\[.*\])", line)
        if fields is None:
            raise ValueError("host pipeline timing is missing fields")
        duration, shaders, data = fields.groups()
        duration = int(duration)
        phases = ast.literal_eval(data)
        if not phases or phases[0] != ("bindings", 0):
            raise ValueError("host pipeline timing has no start")
        bounds = [offset for _, offset in phases] + [duration]
        if bounds != sorted(bounds) or any(phase not in stages for phase, _ in phases):
            raise ValueError("host pipeline timing has invalid phases")
        if shaders.startswith("[compute ") and "," not in shaders:
            start = end - duration
            spans = [(phase, start + left, start + right)
                     for (phase, left), right in zip(phases, bounds[1:])]
            traces.setdefault(shaders, []).append(spans)

    covered = {phase: [] for phase in stages}
    matched = 0
    for _, start, end, line in _pipeline_wait_reports(waits, launched, stop):
        shaders = re.search(r"\bshaders=(\[[^\]]+\])", line)
        if shaders is None:
            raise ValueError("compute wait has no shader list")
        trace = traces.get(shaders[1])
        if trace is None or len(trace) != 1:
            continue
        matched += 1
        for phase, left, right in trace[0]:
            lo, hi = max(start, left), min(end, right)
            if lo < hi:
                covered[phase].append((lo, hi))
    gaps = _complete_long_gaps(frames, stop)
    for spans in covered.values():
        spans.sort()
    all_spans = sorted(span for spans in covered.values() for span in spans)
    created = [(left, right)
               for entries in traces.values() for spans in entries for phase, left, right in spans
               if phase == "driver_create" and left < right]
    create_by_gap = []
    for left, right in gaps:
        active = [(max(left, start), min(right, end)) for start, end in created
                  if start < right and end > left]
        edges = sorted(edge for start, end in active for edge in ((start, 1), (end, -1)))
        running = peak = 0
        for _, change in edges:
            running += change
            peak = max(peak, running)
        create_by_gap.append({
            "start_seconds": left / 1e6,
            "end_seconds": right / 1e6,
            "calls": len(active),
            "overlapping_worker_seconds": sum(end - start for start, end in active) / 1e6,
            "peak_concurrent_calls": peak,
        })
    return {
        "compute_pipeline_traces": sum(map(len, traces.values())),
        "compute_wait_reports": len(waits),
        "matched_compute_wait_reports": matched,
        "overlap_by_stage_seconds": {
            phase: sum(_wait_overlap(spans, a, b) for a, b in gaps) / 1e6
            for phase, spans in covered.items()
        },
        "any_stage_overlap_seconds": sum(_wait_overlap(all_spans, a, b) for a, b in gaps) / 1e6,
        "driver_create_by_gap": create_by_gap,
    }


def verify_constructor_pool(lines, launched, stop, expected):
    label = "host list reuse at construction"
    seen = set()
    for _, line in windowed_log_lines(lines, launched, stop, (label,)):
        outcome = re.search(r"\breuse=(true|false)\b", line)
        if outcome is None:
            raise ValueError("host list reuse log has no flag")
        seen.add(outcome[1] == "true")
    if seen != {expected}:
        raise ValueError("host list reuse does not match the requested mode")


def verify_notification_mode(lines, launched, stop, expected):
    label = "pipeline completion notification mode"
    observed = set()
    for _, line in windowed_log_lines(lines, launched, stop, (label,)):
        match = re.search(r"\blocal=(true|false)\b", line)
        if match is None:
            raise ValueError("pipeline completion notification mode was not logged")
        observed.add(match[1] == "true")
    if observed != {expected}:
        raise ValueError("pipeline completion notifications do not match the requested mode")
