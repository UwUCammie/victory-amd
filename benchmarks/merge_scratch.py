"""Measure scratch reuse in the exact renderer piece merge on generated buffers."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def source_at(checkout, revision):
    return subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/shadow.rs"], text=True
    )


def kernel(source, name):
    return re.search(rf"^fn {name}\(.*?^}}", source, re.M | re.S)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    left = source_at(args.checkout, args.control)
    right = source_at(args.checkout, args.candidate)
    shared = [kernel(left, name) for name in ("first_difference", "last_difference")]
    if shared != [kernel(right, name) for name in ("first_difference", "last_difference")]:
        parser.error("difference scans changed between revisions")
    chunk = re.search(r"^const DIFF_CHUNK: usize = \d+;", left, re.M)[0]
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="merge-scratch-") as tmp:
        rust = Path(tmp) / "bench.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text("\n".join([
            chunk, *shared, kernel(left, "back_piece").replace("fn back_piece(", "fn control("),
            kernel(right, "back_piece").replace("fn back_piece(", "fn candidate("), fixture
        ]), encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
