"""Measure both versions of the copy pool using the same workload and compiler."""
import argparse
from collections import defaultdict
from pathlib import Path
from shutil import copyfile
from statistics import median
import subprocess
import tempfile


def pool_at(revision):
    path = "crates/victory-gpu/src/shadow.rs"
    source = subprocess.check_output(["git", "show", f"{revision}:{path}"], text=True)
    start = source.index("type Job = Box<dyn FnOnce() + Send>;")
    end = source.index("/// About this many bytes to a piece", start)
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        copyfile(Path(__file__).with_name("copy_pool.rs"), root / "main.rs")
        for name, revision in [("before", args.before), ("after", args.after)]:
            (root / f"{name}.rs").write_text(pool_at(revision), encoding="utf-8")
        exe = root / "pool_bench"
        subprocess.run(["rustc", "--edition=2024", "-O", "-o", str(exe), str(root / "main.rs")], check=True)
        result = subprocess.check_output([str(exe)], text=True)
    samples = defaultdict(lambda: defaultdict(list))
    for line in result.splitlines():
        jobs, callers, updates, pair, after, micros = line.split()
        samples[(jobs, callers, updates)][after].append(int(micros) / 1000)
    for (jobs, callers, updates), times in samples.items():
        print(f"{jobs} jobs, {callers} callers, update buffers {updates}: "
              f"{median(times['false']):.2f} ms before, {median(times['true']):.2f} ms after")


if __name__ == "__main__":
    main()
