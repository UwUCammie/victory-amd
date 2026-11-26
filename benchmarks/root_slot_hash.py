"""Compare renderer address hashing with RandomState on synthetic root slots."""
import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ADDRESS_HASH = re.compile(r"^#\[derive\(Default\)\]\npub\(crate\) struct AddressHash.*?^}", re.M | re.S)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="VIctory checkout with AddressHash in victory-gpu/src/host.rs")
    args = parser.parse_args()
    source = (args.checkout / "crates/victory-gpu/src/host.rs").read_text()
    actual = ADDRESS_HASH.search(source)
    if actual is None:
        parser.error("could not locate the renderer's AddressHash implementation")
    bench = Path(__file__).with_suffix(".rs").read_text()
    with TemporaryDirectory(prefix="root-slot-hash-") as tmp:
        rust = Path(tmp) / "root_slot_hash.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text(actual[0] + "\n" + bench)
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        print("keys,pair,random_state_ns_per_list,address_hash_ns_per_list", flush=True)
        subprocess.run([str(exe)], check=True)
