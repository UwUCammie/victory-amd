"""Compare two revisions of the renderer's reverse byte scan on synthetic data."""

import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

SHADOW = "crates/victory-gpu/src/shadow.rs"
SCAN = re.compile(r"^fn last_difference\(a: &\[u8\].*?^}", re.M | re.S)
AVX2 = re.compile(
    r'^#\[cfg\(target_arch = "x86_64"\)\]\n#\[target_feature\(enable = "avx2"\)\]\n'
    r"fn last_difference_avx2\(.*?^}",
    re.M | re.S,
)


def read_scan(checkout, revision):
    source = subprocess.check_output(
        ["git", "-C", str(checkout), "show", f"{revision}:{SHADOW}"], text=True
    )
    scan = SCAN.search(source)
    if not scan:
        raise ValueError(f"reverse scan not found in {revision}")
    return scan[0], AVX2.search(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("control")
    parser.add_argument("candidate")
    args = parser.parse_args()
    control, control_avx2 = read_scan(args.checkout, args.control)
    candidate, candidate_avx2 = read_scan(args.checkout, args.candidate)
    if control_avx2 or not candidate_avx2:
        parser.error("expected a scalar control and an AVX2 candidate")
    fixture = Path(__file__).with_suffix(".rs").read_text(encoding="utf-8")
    with TemporaryDirectory(prefix="last-difference-") as tmp:
        rust = Path(tmp) / "last_difference.rs"
        exe = rust.with_suffix(".exe")
        rust.write_text(
            "\n".join([
                "const DIFF_CHUNK: usize = 32;",
                control.replace("fn last_difference(", "fn control("),
                candidate.replace("fn last_difference(", "fn candidate("),
                candidate_avx2[0],
                fixture,
            ]),
            encoding="utf-8",
        )
        subprocess.run(["rustc", "--edition=2024", "-O", str(rust), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
