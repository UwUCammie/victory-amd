"""Time the journal part of a texture refresh on synthetic write history."""
import argparse
from pathlib import Path
from statistics import median
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="revision containing the unchanged_since query")
    parser.add_argument("--pairs", type=int, default=7)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("at least one pair is required")
    path = "crates/victory-gpu/src/watch.rs"
    source = subprocess.check_output(["git", "show", f"{args.revision}:{path}"], text=True)
    methods = []
    for name in ("writes", "unchanged_since"):
        start = source.index(f"pub(crate) fn {name}(")
        methods.append(source[start:source.index("\n}", start) + 2])
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as temp:
        rust = Path(temp) / "texture_query.rs"
        exe = Path(temp) / "texture_query.exe"
        rust.write_text(fixture.replace("// MEASURED_SOURCE", "\n".join(methods)), encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", rust, "-o", exe], check=True)
        samples = {}
        for pair in range(args.pairs):
            for mode in (("list", "summary") if pair % 2 == 0 else ("summary", "list")):
                output = subprocess.check_output([exe, mode], text=True)
                for line in output.splitlines():
                    case, ns = line.split()
                    samples.setdefault(case, {}).setdefault(mode, []).append(int(ns))
        for case, row in samples.items():
            wins = sum(new < old for old, new in zip(row["list"], row["summary"]))
            print(f'{case}: list {median(row["list"]):g} ns, summary {median(row["summary"]):g} ns, '
                  f'{wins}/{args.pairs} faster')


if __name__ == "__main__":
    main()
