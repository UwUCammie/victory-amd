"""Compile the renderer's range-selection helper and time generated requests."""

from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
import subprocess


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--scratch", type=Path)
    args = parser.parse_args()
    source = (args.checkout / "crates/victory-gpu/src/watch.rs").read_text(encoding="utf-8")
    start = source.index("fn record_uncovered(")
    end = source.index("\n/// [`ask_once`] after", start)
    methods = source[start:end]
    flags = ["--cfg=adaptive"] if "struct RestRanges" in methods else []
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="write-watch-ranges-", dir=args.scratch) as directory:
        root = Path(directory)
        program = root / "ranges.rs"
        program.write_text(methods + "\n" + fixture, encoding="utf-8", newline="\n")
        exe = root / "ranges"
        subprocess.run(["rustc", "--edition=2024", "-O", *flags, str(program), "-o", str(exe)], check=True)
        lines = subprocess.check_output([str(exe)], text=True).splitlines()
    print(lines[0])
    sizes = defaultdict(list)
    for row in lines[1:]:
        case, size, count, original, candidate = row.split(",")
        sizes[case, int(size), int(count)].append((int(original), int(candidate)))
    for (case, size, count), pairs in sizes.items():
        original, candidate = zip(*pairs)
        change = 100 * (median(new / old for old, new in pairs) - 1)
        print(f"{case:9} {size:4} inputs {count:4} requests {median(original):9.0f} -> {median(candidate):9.0f} ns ({change:+.1f}%)")


if __name__ == "__main__":
    main()
