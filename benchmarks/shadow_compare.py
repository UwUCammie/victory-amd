"""Prepare the Wine byte-comparison fixture or summarize its paired timings."""
import argparse
from pathlib import Path
from statistics import median


def prepare(checkout, output):
    path = checkout / "crates/victory-gpu/src/safecopy.rs"
    source = path.read_text(encoding="utf-8")
    start = source.index("pub(crate) unsafe fn differ(")
    method = source[start:source.index("\n}", start) + 2]
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    output.write_text(fixture.replace("// MEASURED_SOURCE", method), encoding="utf-8", newline="\n")


def report(path):
    results = {}
    data = path.read_bytes()
    # Windows PowerShell 5 redirects native output to UTF-16; Wine and newer shells use UTF-8.
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    for line in data.decode(encoding).splitlines():
        case, pair, method, ns = line.split()
        key = (case, int(pair), method)
        if key in results or int(ns) < 0:
            raise ValueError(f"invalid or duplicate timing: {key}")
        results[key] = int(ns)
    cases = ("equal", "first", "middle", "last")
    pairs = range(1, 9)
    if set(results) != {(case, pair, method) for case in cases for pair in pairs for method in ("slice", "avx2")}:
        raise ValueError("expected both methods in every pair for all four cases")
    for case in cases:
        old = [results[case, pair, "slice"] for pair in pairs]
        new = [results[case, pair, "avx2"] for pair in pairs]
        wins = sum(a < b for a, b in zip(new, old))
        print(f"{case}: slice {median(old):g} ns, avx2 {median(new):g} ns, faster in {wins}/{len(old)} pairs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("checkout", type=Path)
    prep.add_argument("output", type=Path)
    show = sub.add_parser("report")
    show.add_argument("results", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.checkout, args.output)
    else:
        report(args.results)


if __name__ == "__main__":
    main()
