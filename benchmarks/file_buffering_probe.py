"""Check the host FDs used by Wine for two synchronous Win32 open modes."""

import argparse
import json
import os
from pathlib import Path
import select
import subprocess
from tempfile import TemporaryDirectory


def win_path(path):
    return "Z:" + str(path).replace("/", "\\")


def open_flags(proc_pid, paths):
    found = {str(path): set() for path in paths}
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            if proc.name != str(proc_pid) and not (proc / "comm").read_text().startswith("wineserver"):
                continue
            for fd in (proc / "fd").iterdir():
                try:
                    target = os.readlink(fd)
                    if target in found:
                        values = dict(line.split(":", 1) for line in (proc / "fdinfo" / fd.name).read_text().splitlines())
                        found[target].add(int(values["flags"], 8))
                except (OSError, KeyError, ValueError):
                    continue
        except OSError:
            continue
    return [sorted(found[str(path)]) for path in paths]


def run(wine, executable):
    with TemporaryDirectory(prefix="wine-file-mode-probe-") as scratch:
        work = Path(scratch)
        paths = [work / name for name in ("buffered.bin", "unbuffered.bin")]
        block = bytes((7 * i + i // 257) & 255 for i in range(4096))
        for path in paths:
            path.write_bytes(block + block)
        with subprocess.Popen([wine, str(executable), *map(win_path, paths)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as proc:
            try:
                if not select.select([proc.stdout], [], [], 20)[0]:
                    raise TimeoutError("Wine probe did not open both files")
                marker, *modes = proc.stdout.readline().split()
                if marker != "ready" or len(modes) != 2:
                    raise ValueError("missing Win32 open-mode witness")
                flags = open_flags(proc.pid, paths)
                if not all(flags):
                    raise ValueError("could not observe both Unix file descriptors")
                result = {"windows_mode": modes, "unix_flags": [[oct(f) for f in group] for group in flags],
                          "o_direct": [[bool(f & os.O_DIRECT) for f in group] for group in flags]}
            finally:
                _, _ = proc.communicate("\n", timeout=8)
            if proc.returncode != 0:
                raise ValueError(f"Wine probe exited {proc.returncode}")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--wine", default="wine")
    args = parser.parse_args()
    print(json.dumps(run(args.wine, args.executable.resolve()), indent=2))
