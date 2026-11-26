"""Detect other Linux render clients by executable or by cgroup and GPU node."""
import argparse
import os
from pathlib import Path
import sys


def node_fds(process, node):
    for fd in (process / "fd").iterdir():
        try:
            if os.readlink(fd) == node:
                yield fd.name
        except OSError:
            continue


def fdinfo(process, fd):
    try:
        fields = (process / "fdinfo" / fd).read_text().splitlines()
    except OSError:
        return {}
    return {k: v.strip() for k, _, v in (line.partition(":") for line in fields)}


def in_group(process, groups):
    for line in (process / "cgroup").read_text().splitlines():
        if line.startswith("0::"):
            return bool(groups.intersection(Path(line[3:]).parts))
    return False


def launcher_clients(process, groups, node):
    """DRM clients of the first ancestor outside the monitored job groups."""
    while True:
        status = (process / "status").read_text().splitlines()
        parent = next((line.split()[1] for line in status if line.startswith("PPid:")), "0")
        if parent in ("0", "1"):
            return set()
        process = process.parent / parent
        if not in_group(process, groups):
            return {fdinfo(process, fd).get("drm-client-id") for fd in node_fds(process, node)}


def holds_node(process, node, groups, ignore_inherited_idle):
    inherited = None
    for fd in node_fds(process, node):
        if not ignore_inherited_idle:
            return True
        info = fdinfo(process, fd)
        client = info.get("drm-client-id")
        # Only ignore a confirmed, unused launcher client on this same node.
        # Require the VRAM counter, and check each reported engine counter.
        if (not client or info.get("drm-resident-vram", "").split()[:1] != ["0"]
                or any(v.split()[:1] != ["0"] for k, v in info.items()
                       if k.startswith(("drm-engine-", "drm-cycles-")))):
            return True
        if inherited is None:
            try:
                inherited = launcher_clients(process, groups, node)
            except OSError:
                return True
        if client not in inherited:
            return True
    return False


def busy(proc, executables, groups, node, ignore_inherited_idle=False, explain=False):
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        if executables:
            try:
                executable = Path(os.readlink(process / "exe")).name
                if executable in executables:
                    if explain:
                        print(f"{process.name} runs {executable}", file=sys.stderr)
                    return True
            except OSError:
                pass
        try:
            if groups and in_group(process, groups) and holds_node(process, node, groups, ignore_inherited_idle):
                if explain:
                    print(f"{process.name} holds {node}", file=sys.stderr)
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", action="append", default=[], help="an independent game's executable basename")
    parser.add_argument("--group", action="append", default=[], help="exact cgroup v2 path component of other jobs")
    parser.add_argument("--node", type=Path, help="render node for the benchmark GPU, required with --group")
    parser.add_argument("--ignore-inherited-idle", action="store_true",
                        help="ignore idle DRM clients inherited from the job launcher on a dedicated GPU")
    parser.add_argument("--explain", action="store_true", help="print the blocking process ID to stderr")
    args = parser.parse_args()
    if not (args.executable or args.group) or (args.group and not args.node):
        parser.error("supply --executable or both --group and --node")
    sys.exit(0 if busy(Path("/proc"), set(args.executable), set(args.group),
                       str(args.node.resolve()) if args.node else "", args.ignore_inherited_idle, args.explain) else 1)
