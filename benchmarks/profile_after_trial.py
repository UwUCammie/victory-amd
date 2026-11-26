"""Sample the Wine renderer after its last measured block. Requires perf and llvm-symbolizer."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import tempfile
import time


def image_layout(exe, pid):
    st = exe.stat()
    with open(f"/proc/{pid}/maps", encoding="utf-8", errors="replace") as mappings:
        for row in mappings:
            bounds, _, offset, dev, inode, *path = row.rstrip("\n").split(maxsplit=5)
            major, minor = (int(part, 16) for part in dev.split(":"))
            if int(inode) != st.st_ino or int(offset, 16) != 0:
                continue
            # On Btrfs /proc/maps may report the device of the filesystem while
            # stat reports the subvolume device. Check in the target mount namespace.
            same_file = os.makedev(major, minor) == st.st_dev
            if not same_file and path and path[0].startswith("/"):
                try:
                    same_file = exe.samefile(f"/proc/{pid}/root{path[0]}")
                except OSError:
                    pass
            if same_file:
                load = int(bounds.split("-")[0], 16)
                break
        else:
            raise ValueError("The supplied runtime image is not mapped by this process")
    with exe.open("rb") as stream:
        stream.seek(60)
        stream.seek(struct.unpack("<I", stream.read(4))[0])
        header = stream.read(24 + 60)
    if header[:6] != b"PE\0\0\x64\x86" or struct.unpack_from("<H", header, 24)[0] != 0x20B:
        raise ValueError("Expected the 64-bit x86 Windows runtime image")
    preferred = struct.unpack_from("<Q", header, 24 + 24)[0]
    size = struct.unpack_from("<I", header, 24 + 56)[0]
    return load, preferred, size


def wait_for_block(log, kind, pid, timeout):
    # A PID file descriptor stays attached to this process even if the PID is reused.
    poll = select.poll()
    poll.register(pid, select.POLLIN)
    deadline = time.monotonic() + timeout
    marker = re.compile(r'\bvictory_bench: renderer trial\s+kind="' + re.escape(kind) + r'"\s+block=8\b')
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    with log.open(encoding="utf-8", errors="replace") as stream:
        partial = ""
        while time.monotonic() < deadline and not poll.poll(0):
            line = stream.readline()
            if line:
                partial += line
                if partial.endswith("\n"):
                    if marker.search(ansi.sub("", partial)):
                        return
                    partial = ""
            else:
                time.sleep(0.1)
    raise ValueError("The process exited or the wait expired before block eight")


def summarize(exe, layout, recording):
    load, preferred, size = layout
    output = subprocess.check_output(["perf", "script", "-i", str(recording), "-F", "ip"], text=True)
    ips = Counter()
    total = 0
    for raw in output.splitlines():
        raw = raw.strip()
        if re.fullmatch(r"[0-9a-fA-F]+", raw):
            total += 1
            ip = int(raw, 16)
            if load <= ip < load + size:
                ips[preferred + ip - load] += 1
    if not ips:
        raise ValueError("No user-mode samples landed in the supplied runtime image")
    names = subprocess.check_output(
        ["llvm-symbolizer", "--no-inlines", "--output-style=JSON", "--obj", str(exe)],
        input="".join(f"0x{ip:x}\n" for ip in ips), text=True,
    ).splitlines()
    funcs = Counter()
    for count, line in zip(ips.values(), names, strict=True):
        frames = json.loads(line)["Symbol"]
        symbol = frames[0]["FunctionName"] if frames else ""
        symbol = re.sub(r"(::h[0-9a-f]{16}| \(\.llvm\.\d+\))$", "", symbol) or "??"
        funcs[symbol] += count
    if len(funcs) == 1 and "??" in funcs:
        raise ValueError("No runtime symbols resolved; check the matching PDB beside the executable")
    return total, ips.total(), funcs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("exe", type=Path, help="runtime executable, with its matching PDB alongside")
    parser.add_argument("pid", type=int, help="Linux PID of the running Wine game process")
    parser.add_argument("kind", help="renderer trial kind in the block record")
    parser.add_argument("--seconds", type=int, default=5)
    parser.add_argument("--wait", type=int, default=600)
    args = parser.parse_args()
    if min(args.seconds, args.wait) < 1:
        parser.error("durations must be positive")
    exe = args.exe.resolve(strict=True)
    pidfd = os.pidfd_open(args.pid)
    try:
        layout = image_layout(exe, args.pid)
        wait_for_block(args.log, args.kind, pidfd, args.wait)
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "perf.data"
            subprocess.run(["perf", "record", "-q", "-F", "499", "-e", "cpu-clock:u",
                            "-p", str(args.pid), "-o", str(data), "--", "sleep", str(args.seconds)], check=True)
            if select.select([pidfd], [], [], 0)[0]:
                raise ValueError("The process exited before profiling completed")
            total, samples, funcs = summarize(exe, layout, data)
    finally:
        os.close(pidfd)
    print(f"{args.seconds} s after block eight: {samples} runtime-image samples out of {total} user-mode samples")
    for name, count in funcs.most_common(12):
        print(f"{count:6d} {100 * count / samples:5.1f}%  {name}")


if __name__ == "__main__":
    main()
