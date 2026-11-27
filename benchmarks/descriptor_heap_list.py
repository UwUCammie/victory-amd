"""Check descriptor heap order and temporary allocations using the exact binding blocks."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def block(checkout, revision, name):
    source = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/draw.rs"],
        text=True,
    )
    code = re.search(r"^ {12}let mut heaps[^\n]*\n.*?(?=^ {12}self\.host_heaps = self\.heaps;)",
                     source, re.M | re.S)
    if code is None:
        raise ValueError(f"descriptor binding block missing at {revision}")
    return (f"fn {name}(view_heap: Heap, sampler_heap: Heap) -> Trace {{\n"
            "let l = Bound::default();\nlet list = Kept::default();\n"
            + code[0] + "\nTrace { bound: l.0.get(), kept: list.0.get() }\n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    sources = [block(args.checkout, rev, name) for rev, name in
               [(args.control, "control"), (args.candidate, "candidate")]]
    with TemporaryDirectory(prefix="descriptor-heaps-") as tmp:
        rust = Path(tmp) / "descriptor_heaps.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text("\n".join([*sources, fixture]), encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
