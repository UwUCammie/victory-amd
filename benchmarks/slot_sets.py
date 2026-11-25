"""Compare descriptor slot bookkeeping using the supplied revision of SlotSet."""
from pathlib import Path
import subprocess
import sys
import tempfile


def main(ref):
    path = "crates/victory-gpu/src/descriptor/host.rs"
    host = subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
    start = host.index("#[derive(Default)]\nstruct SlotSet {")
    end = host.index("pub(crate) struct HostHeap", start)
    benchmark = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        trial = Path(tmp) / "slot_sets.rs"
        trial.write_text(host[start:end] + benchmark, encoding="utf-8", newline="\n")
        output = Path(tmp) / ("slot_sets.exe" if sys.platform == "win32" else "slot_sets")
        subprocess.run(["rustc", "--edition=2024", "-O", trial, "-o", output], check=True)
        subprocess.run([output], check=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 benchmarks/slot_sets.py REVISION")
    main(sys.argv[1])
