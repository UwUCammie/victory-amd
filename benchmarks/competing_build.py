"""Return success while a parallel native build can interfere with frame timings."""
from pathlib import Path
import re
import sys

COMPILER = re.compile(r"(?:cc1|cc1plus|rustc|clang(?:\+\+|-cl)?(?:-\d+)?)")


def parallel_build(name, args):
    if name not in (b"make", b"gmake", b"ninja", b"ninja-build"):
        return False
    for i, arg in enumerate(args):
        if arg == b"-j":
            value = args[i + 1] if i + 1 < len(args) else b""
            return not value.isdigit() or int(value) >= 3
        if arg.startswith(b"-j") and arg[2:].isdigit():
            return int(arg[2:]) >= 3
        if arg.startswith(b"--jobs=") and arg[7:].isdigit():
            return int(arg[7:]) >= 3
    return False


def busy(proc):
    compilers = 0
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            name = (entry / "comm").read_bytes().strip()
            if name in (b"make", b"gmake", b"ninja", b"ninja-build"):
                args = (entry / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")[1:]
                if parallel_build(name, args):
                    return True
            elif COMPILER.fullmatch(name.decode("ascii", errors="replace")):
                state = (entry / "stat").read_bytes().rsplit(b") ", 1)[1].split(maxsplit=1)[0]
                if state in (b"R", b"S", b"D"):
                    compilers += 1
                    if compilers >= 3:
                        return True
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return False


if __name__ == "__main__":
    sys.exit(0 if busy(Path("/proc")) else 1)
