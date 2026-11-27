"""Time the exact due-slot collectors on matching generated B-tree queues."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def source_at(checkout, revision):
    return subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:crates/victory-gpu/src/descriptor/host.rs"],
        text=True,
    )


def method(source, name):
    return re.search(rf"^    fn {name}\(.*?^    }}", source, re.M | re.S)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    old = source_at(args.checkout, args.control)
    new = source_at(args.checkout, args.candidate)
    entry = re.search(r"^struct Waiting \{.*?^\}", old, re.M | re.S)[0]
    methods = (method(old, "all_due"), method(old, "census"), method(new, "snapshot"))
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="texture-queue-snapshot-") as tmp:
        path = Path(tmp) / "fixture.rs"
        executable = path.with_suffix(".exe")
        path.write_text("#[allow(dead_code)]\n" + entry + "\nimpl Queue {\n" + "\n".join(methods) + "\n}\n" + fixture,
                        encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(path), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
