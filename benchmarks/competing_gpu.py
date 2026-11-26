"""Detect other Linux render clients by executable or by cgroup and GPU node."""
import argparse
import os
from pathlib import Path
import sys


def holds_node(process, node):
    for fd in (process / "fd").iterdir():
        try:
            if os.readlink(fd) == node:
                return True
        except (OSError, ValueError):
            continue
    return False


def busy(proc, executables, groups, node):
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if executables and Path(os.readlink(process / "exe")).name in executables:
                return True
            if groups:
                for line in (process / "cgroup").read_text().splitlines():
                    if line.startswith("0::") and groups.intersection(Path(line[3:]).parts):
                        if holds_node(process, node):
                            return True
                        break
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", action="append", default=[], help="an independent game's executable basename")
    parser.add_argument("--group", action="append", default=[], help="exact cgroup v2 path component of other jobs")
    parser.add_argument("--node", type=Path, help="render node for the benchmark GPU, required with --group")
    args = parser.parse_args()
    if not (args.executable or args.group) or (args.group and not args.node):
        parser.error("supply --executable or both --group and --node")
    sys.exit(0 if busy(Path("/proc"), set(args.executable), set(args.group),
                       str(args.node.resolve()) if args.node else "") else 1)
