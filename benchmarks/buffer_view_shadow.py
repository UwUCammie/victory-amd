"""Compare the exact buffer-view copy selectors with generated buffer ranges."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def selector(checkout, revision, name):
    source = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/descriptor/host.rs"],
        text=True,
    )
    methods = [re.search(rf"^fn {method}\(.*?^}}", source, re.M | re.S)[0] for method in (name, "off_elements")]
    return "\n".join(methods)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    control = selector(args.checkout, args.control, "view_home")
    candidate = selector(args.checkout, args.candidate, "separate_view_copy")
    old, new = (src[src.index("fn off_elements"):].strip() for src in (control, candidate))
    if old != new:
        raise ValueError("selector revisions have different alignment rules")
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="buffer-view-shadow-") as tmp:
        rust = Path(tmp) / "bench.rs"
        output = rust.with_suffix(".exe")
        rust.write_text(control + "\n" + candidate[:candidate.index("fn off_elements")] + "\n" + fixture,
                        encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(output)], check=True)
        subprocess.run([str(output)], check=True)
