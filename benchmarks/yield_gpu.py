"""Stop a benchmark's gamescope timeout if a foreground game needs the GPU (Linux)."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time


def scoped_timeout(proc, unit):
    try:
        if proc.stat().st_uid != os.getuid():
            return False
        command = (proc / "cmdline").read_bytes().split(b"\0")
        scope = (proc / "cgroup").read_text().splitlines()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return False
    return (Path(os.fsdecode(command[0])).name == "timeout"
            and command[1:3] == [b"-k", b"5"] and command[4:5] == [b"gamescope"]
            and any(line.startswith("0::") and Path(line[3:]).name == unit for line in scope))


def yield_timeouts(units):
    for proc in Path("/proc").glob("[0-9]*"):
        if not any(scoped_timeout(proc, unit) for unit in units):
            continue
        try:
            fd = os.pidfd_open(int(proc.name))
        except ProcessLookupError:
            continue
        try:
            if any(scoped_timeout(proc, unit) for unit in units):
                signal.pidfd_send_signal(fd, signal.SIGTERM)
                print(f"Yielded benchmark timeout {proc.name}", flush=True)
        except ProcessLookupError:
            pass
        finally:
            os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", action="append", required=True, help="dedicated benchmark service (repeatable)")
    parser.add_argument("busy", nargs="+", help="command returning zero while the GPU is in foreground use")
    args = parser.parse_args()
    if any(not unit.endswith(".service") or "/" in unit for unit in args.unit):
        parser.error("expected service names")
    while any(subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit]).returncode == 0 for unit in args.unit):
        if subprocess.run(args.busy).returncode == 0:
            yield_timeouts(args.unit)
        time.sleep(1)
