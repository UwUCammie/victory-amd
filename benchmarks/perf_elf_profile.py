"""Summarize exact-build native ELF samples without exporting addresses."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess


def build_id(binary):
    notes = subprocess.check_output(["readelf", "-n", binary], text=True)
    ids = set(re.findall(r"Build ID: ([0-9a-f]+)", notes))
    if len(ids) != 1:
        raise ValueError("cannot identify a unique ELF build ID")
    return ids.pop()


def code_segments(binary):
    headers = subprocess.check_output(["readelf", "-Wl", binary], text=True)
    segments = []
    for line in headers.splitlines():
        fields = line.split()
        if fields and fields[0] == "LOAD" and "E" in fields[6:-1]:
            offset, address, size = (int(fields[i], 16) for i in (1, 2, 4))
            segments.append((offset, offset + size, address))
    if not segments:
        raise ValueError("ELF has no executable load segment")
    return segments


def samples(capture, binary, expected_id, segments, thread):
    ids = subprocess.check_output(["perf", "buildid-list", "-i", capture], text=True)
    if (expected_id, str(binary)) not in {tuple(line.split(maxsplit=1)) for line in ids.splitlines()}:
        raise ValueError("driver build ID differs from the recorded mapping")
    rows = subprocess.check_output(
        ["perf", "script", "-i", capture, "-F", "comm,ip,sym,dso,dsoff"], text=True
    )
    offset_pattern = re.compile(rf"\({re.escape(str(binary))}\+0x([0-9a-f]+)\)$")
    offsets = Counter(int(match[1], 16) for row in rows.splitlines()
                      if row.lstrip().split(maxsplit=1)[:1] == [thread]
                      if (match := offset_pattern.search(row.rstrip())))
    addresses = Counter()
    for offset, count in offsets.items():
        addresses.update({address + offset - start: count
                          for start, end, address in segments if start <= offset < end})
    if not addresses or sum(addresses.values()) != sum(offsets.values()):
        raise ValueError("sample offsets do not match executable ELF segments")
    return addresses


def read_symbols(debug, addresses):
    response = subprocess.run(
        ["addr2line", "-a", "-f", "-C", "-i", "-e", debug],
        input="".join(f"{address:#x}\n" for address in sorted(addresses)),
        text=True, capture_output=True, check=True,
    )
    symbols = {}
    rows = iter(response.stdout.splitlines())
    for row in rows:
        if re.fullmatch(r"0x[0-9a-f]+", row):
            frames = symbols.setdefault(int(row, 16), [])
            continue
        location = next(rows, "")
        source = re.search(r"(src/(?:compiler|amd|vulkan|util)/.+):\d+(?: .*)?$", location)
        if source:
            frames.append((source[1], row))
    if symbols.keys() != addresses:
        raise ValueError("symbolizer did not return one record per address")
    return symbols


def summarize(counts, symbols):
    modules = Counter()
    files = Counter()
    functions = Counter()
    for address, count in counts.items():
        frames = symbols[address]
        if not frames:
            modules["unresolved"] += count
            continue
        path = frames[0][0]
        parts = path.split("/")
        module = "/".join(parts[:3] if parts[1] in ("amd", "compiler") and len(parts) > 3 else parts[:2])
        modules[module] += count
        files[path] += count
        for name in {name for _, name in frames if name}:
            functions[name] += count
    return {
        "module_samples": sum(counts.values()),
        "leaf_subsystems": dict(modules.most_common()),
        "leaf_source_samples": files.most_common(12),
        "inline_function_samples": functions.most_common(18),
    }


def profile(binary, debug, captures, thread):
    expected = build_id(binary)
    if build_id(debug) != expected:
        raise ValueError("ELF and debug symbols have different build IDs")
    segments = code_segments(binary)
    counts = [samples(capture, binary, expected, segments, thread) for capture in captures]
    addresses = set().union(*counts)
    symbols = read_symbols(debug, addresses)
    return {"build_id": expected, "captures": [summarize(capture, symbols) for capture in counts]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("debug", type=Path)
    parser.add_argument("captures", nargs="+", type=Path)
    parser.add_argument("--thread", default="victory-pipelin")
    args = parser.parse_args()
    try:
        result = profile(args.binary, args.debug, args.captures, args.thread)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))
