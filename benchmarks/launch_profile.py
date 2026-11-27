"""Collect a user-mode CPU profile from one guarded Wine benchmark launch."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time

from profile_after_trial import image_layout


def runtime_pid(proc, executable, overlap):
    args = [os.fsencode(executable), b"run"]
    marker = b"GOAL30_YIELD_MARKER=" + os.fsencode(overlap)
    matches = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if (entry / "cmdline").read_bytes().split(b"\0", 2)[:2] != args:
                continue
            if marker in (entry / "environ").read_bytes().split(b"\0"):
                matches.append(int(entry.name))
        except OSError:
            continue
    if len(matches) != 1:
        raise ValueError("expected one Wine process for the profiling launch")
    return matches[0]


def elapsed_seconds(start):
    return (datetime.now(timezone.utc) - start).total_seconds()


def capture(launch_path, executable, after, seconds):
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    if not launch["diagnostic_only"] or "end_utc" in launch:
        raise ValueError("expected a live diagnostic launch")
    executable = executable.resolve(strict=True)
    with executable.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != launch["executable_sha256"]:
            raise ValueError("executable does not match the launch")
    launched = datetime.fromisoformat(launch["start_utc"])
    deadline = time.monotonic() + after - elapsed_seconds(launched)
    while (remaining := deadline - time.monotonic()) > 0:
        time.sleep(remaining)
    overlap = launch_path.with_name("foreground-overlap")
    if overlap.exists():
        raise ValueError("guard fired before CPU sampling started")
    proc = Path("/proc")
    pid = runtime_pid(proc, executable, overlap)
    fd = os.pidfd_open(pid)
    try:
        load, preferred, size = image_layout(executable, pid)
        if select.select([fd], [], [], 0)[0]:
            raise ValueError("the runtime exited before CPU sampling started")
        began = elapsed_seconds(launched)
        if not after - 0.1 <= began <= after + 3:
            raise ValueError("the runtime missed the requested profiling window")
        data = launch_path.with_name("late-submit.perf.data")
        if data.exists():
            raise ValueError("the profile data file already exists")
        subprocess.run(["perf", "record", "-q", "-F", "499", "-e", "cpu-clock:u",
                        "-p", str(pid), "-o", str(data), "--", "sleep", str(seconds)],
                       check=True, timeout=seconds + 10)
        ended = elapsed_seconds(launched)
        if select.select([fd], [], [], 0)[0] or overlap.exists():
            raise ValueError("the runtime exited or yielded during CPU sampling")
        if not data.stat().st_size:
            raise ValueError("the CPU profile contains no data")
    finally:
        os.close(fd)
    return {"pid": pid, "began_seconds": began, "ended_seconds": ended,
            "image_load": load, "image_preferred": preferred, "image_size": size}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launch", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--after", type=int, required=True)
    parser.add_argument("--seconds", type=int, default=6)
    args = parser.parse_args()
    if min(args.after, args.seconds) < 1:
        parser.error("durations must be positive")
    try:
        print(json.dumps(capture(args.launch, args.executable, args.after, args.seconds)))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")
