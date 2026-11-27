"""Compare bounded texture queue ordering on generated records."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def selection(checkout, revision, name):
    source = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/descriptor/host.rs"],
        text=True,
    )
    method = re.search(r"^    fn in_order\(.*?^    }", source, re.M | re.S)[0]
    return method.replace("fn in_order(", f"fn {name}(", 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="due-texture-order-") as tmp:
        rust = Path(tmp) / "bench.rs"
        output = rust.with_suffix(".exe")
        before = selection(args.checkout, args.control, "control")
        after = selection(args.checkout, args.candidate, "candidate")
        rust.write_text("\n".join((before, after, fixture)), encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(output)], check=True)
        subprocess.run([str(output)], check=True)
