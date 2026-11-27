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
    function = merge[0]
    if "DIFF_CHUNK" in function:
        chunk = re.search(r"^const DIFF_CHUNK: usize = \d+;", source, re.M)
        if chunk is None:
            raise ValueError(f"literal DIFF_CHUNK is missing at {revision}")
        function = function.replace(" {\n", f" {{\n    {chunk[0]}\n", 1)
    helpers = []
    for helper in ("merge_piece_scalar", "merge_piece_avx2"):
        if helper in function:
            block = re.search(rf"(?:^#\[[^\n]+\]\n)*^(?:unsafe )?fn {helper}\(.*?^}}", source, re.M | re.S)
            if block is None:
                raise ValueError(f"{helper} is missing at {revision}")
            helpers.append(block[0])
    return re.sub(r"\bmerge_piece(?=\b|_)", name, "\n".join(("#[inline(never)]\n" + function, *helpers)))


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
