"""Time two versions of the renderer's shadow merge on generated buffers."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def kernel(checkout, revision, name):
    source = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/shadow.rs"],
        text=True,
    )
    merge = re.search(r"^fn merge_piece\(now: &\[u8\].*?^}", source, re.M | re.S)
    if merge is None:
        raise ValueError(f"shadow merge is missing at {revision}")
    return "#[inline(never)]\n" + merge[0].replace("fn merge_piece(", f"fn {name}(")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    parser.add_argument("--cpu", help="optional rustc target CPU")
    args = parser.parse_args()
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    sources = [kernel(args.checkout, args.control, "control"),
               kernel(args.checkout, args.candidate, "candidate"), fixture]
    cpu = ["-C", f"target-cpu={args.cpu}"] if args.cpu else []
    with TemporaryDirectory(prefix="shadow-merge-") as tmp:
        rust = Path(tmp) / "bench.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text("\n".join(sources), encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", *cpu, str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
