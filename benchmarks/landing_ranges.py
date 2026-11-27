"""Benchmark the renderer's landing-range calculations on generated ranges."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def source_at(checkout, revision):
    return subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/shadow.rs"],
        text=True,
    )


def kernel(source, name):
    return re.search(rf"^fn {name}\(.*?^}}", source, re.M | re.S)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    left = source_at(args.checkout, args.control)
    right = source_at(args.checkout, args.candidate)
    with TemporaryDirectory(prefix="landing-ranges-") as tmp:
        rust = Path(tmp) / "bench.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text("\n".join([kernel(left, "outside"), kernel(right, "outside_sorted"), fixture]),
                        encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
