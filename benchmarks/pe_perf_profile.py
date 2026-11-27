"""Attribute anonymous Wine perf samples to an exact executable and its PDB."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from verify_pdb_sources import field, output


def runtime_profile(data, executable, launch, thread, focus=(), capture=None):
    if not launch["diagnostic_only"]:
        raise ValueError("expected a profiling launch")
    with executable.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != launch["executable_sha256"]:
            raise ValueError("executable does not match the profiling launch")
    debug = output("llvm-readobj", "--coff-debug-directory", executable)
    pdb = output("llvm-pdbutil", "dump", "--summary", executable.with_suffix(".pdb"))
    if (field(debug, "PDBGUID"), field(debug, "PDBAge")) != (field(pdb, "GUID"), field(pdb, "Age")):
        raise ValueError("executable and PDB differ")

    headers = output("llvm-readobj", "--file-headers", "--sections", executable)
    image_base = int(field(headers, "ImageBase"), 0)
    align = int(field(headers, "SectionAlignment"), 0)
    code = re.search(r"(?m)^\s*Name: \.text\b[^\n]*\n(.*?)^\s*}", headers, re.S | re.M)
    if code is None:
        raise ValueError("executable has no text section")
    size = int(field(code[1], "VirtualSize"), 0)
    rva = int(field(code[1], "VirtualAddress"), 0)
    mapped_size = (size + align - 1) // align * align

    pattern = r"PERF_RECORD_MMAP2 \d+/\d+: \[(0x[0-9a-f]+)\((0x[0-9a-f]+)\) @ 0 .*\]: r-xp //anon$"
    trace = output("perf", "report", "--dump-raw-trace", "-i", data)
    regions = {int(start, 16) for start, length in re.findall(pattern, trace, re.M)
               if int(length, 16) == mapped_size and (int(start, 16) - rva) % 65536 == 0}
    if capture is not None:
        if capture["image_preferred"] != image_base:
            raise ValueError("captured and executable image bases differ")
        regions.intersection_update({capture["image_load"] + rva})
    if len(regions) != 1:
        raise ValueError("cannot identify a unique anonymous text mapping")
    start = regions.pop()
    end = start + size
    samples = output("perf", "script", "-i", data, "-F", "comm,ip,dso")
    thread_samples = re.findall(rf"(?m)^[ \t]*{re.escape(thread)}\s+([0-9a-f]+)\s+\(([^)\n]*)\)", samples)
    anonymous = Counter(int(ip, 16) for ip, dso in thread_samples if re.search(r"perf-\d+\.map$", dso))
    counts = {hex(image_base + rva + ip - start): count for ip, count in anonymous.items() if start <= ip < end}
    if not counts:
        raise ValueError("no anonymous thread samples match the text mapping")

    response = subprocess.run(
        ["llvm-symbolizer", f"--obj={executable}", "--inlines", "--output-style=JSON"],
        input="\n".join(counts) + "\n", text=True, capture_output=True, check=True,
    )
    functions = Counter()
    files = Counter()
    focused = dict.fromkeys(focus, 0)
    attributed = 0
    for line in response.stdout.splitlines():
        record = json.loads(line)
        hits = counts[record["Address"]]
        locations = set()
        owners = set()
        for symbol in record["Symbol"]:
            source = re.search(r"(?:crates/victory-[\w-]+|apps/victory)/src/[^:]+",
                               symbol["FileName"].replace("\\", "/"))
            if source is None:
                continue
            name = re.sub(r"(?:::closure\$\d+)+$", "", symbol["FunctionName"])
            locations.add(source[0])
            owners.add(name)
        if locations:
            attributed += hits
        for path in locations:
            files[path] += hits
        for name in owners:
            functions[name] += hits
        for name in focused.keys() & {owner.rsplit("::", 1)[-1] for owner in owners}:
            focused[name] += hits

    if not attributed:
        raise ValueError("the text mapping did not resolve to runtime source")
    return {
        "thread_samples": len(thread_samples),
        "anonymous_thread_samples": sum(anonymous.values()),
        "in_text_section": sum(counts.values()),
        "attributed_to_runtime": attributed,
        "requested_function_samples": focused,
        "inclusive_source_samples": files.most_common(12),
        "inclusive_function_samples": functions.most_common(18),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("launch", type=Path)
    parser.add_argument("--thread", default="victory-pipelin")
    parser.add_argument("--capture", type=Path, help="Optional process image metadata from launch_profile.py")
    parser.add_argument("--focus", action="append", default=[],
                        help="Count samples for this function regardless of its rank")
    args = parser.parse_args()
    try:
        capture = json.loads(args.capture.read_text()) if args.capture else None
        result = runtime_profile(args.data, args.executable, json.loads(args.launch.read_text()),
                                 args.thread, args.focus, capture)
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))
