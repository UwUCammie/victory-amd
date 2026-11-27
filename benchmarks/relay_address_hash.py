"""Compare two hashers for synthetic relay readback ranges."""

import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from root_slot_hash import ADDRESS_HASH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="VIctory checkout with the renderer's AddressHash")
    args = parser.parse_args()
    source = (args.checkout / "crates/victory-gpu/src/host.rs").read_text(encoding="utf-8")
    actual = ADDRESS_HASH.search(source)
    if actual is None:
        parser.error("could not locate the renderer's AddressHash implementation")
    bench = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="relay-address-hash-") as tmp:
        rust = Path(tmp) / "relay_address_hash.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text(actual[0] + "\n" + bench, encoding="utf-8", newline="\n")
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
