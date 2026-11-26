"""Compare the two relay flag collectors on generated range flags."""
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = "crates/victory-gpu/src/host.rs"
METHOD = re.compile(r"^fn flagged_pieces\(.*?^}", re.M | re.S)


def get(commit, name):
    source = subprocess.check_output(["git", "show", f"{commit}:{ROOT}"], text=True)
    return METHOD.search(source)[0].replace("fn flagged_pieces(", f"fn {name}(", 1)


FIXTURE = r'''
use std::hint::black_box;
use std::time::Instant;

type Flag = (usize, u32, bool);
type Piece = (usize, u32);

fn baseline(flags: &[Flag]) -> Vec<Piece> {
    let all: Vec<_> = flags.iter().copied().map(black_box).collect();
    old_collector(&all)
}

fn streamed(flags: &[Flag]) -> Vec<Piece> {
    new_collector(flags.iter().copied().map(black_box))
}

fn measure(f: fn(&[Flag]) -> Vec<Piece>, flags: &[Flag], rounds: usize) -> (f64, usize) {
    let start = Instant::now();
    let mut count = 0usize;
    for _ in 0..rounds {
        let kept = f(black_box(flags));
        count += black_box(kept.len());
    }
    (start.elapsed().as_nanos() as f64 / rounds as f64, count)
}

fn main() {
    println!("flags,wanted_quarters,pair,baseline_ns,streamed_ns");
    for size in [64usize, 512, 4096, 16384] {
        for wanted in [1, 4] {
            let flags: Vec<_> = (0..size).map(|i| {
                let copy = 0x10_0000 + ((i / 127).wrapping_mul(13) % 91) * 0x4000;
                let piece = ((i / 2) % 61) as u32;
                let selected = i.wrapping_mul(11) % 4 < wanted;
                (copy, piece, selected)
            }).collect();
            assert_eq!(baseline(&flags), streamed(&flags));
            let rounds = (1_000_000 / size).max(50);
            for pair in 0..7 {
                let (control, candidate) = if pair % 2 == 0 {
                    (measure(baseline, &flags, rounds), measure(streamed, &flags, rounds))
                } else {
                    let candidate = measure(streamed, &flags, rounds);
                    (measure(baseline, &flags, rounds), candidate)
                };
                assert_eq!(control.1, candidate.1);
                println!("{size},{wanted},{pair},{:.3},{:.3}", control.0, candidate.0);
            }
        }
    }
}
'''


if __name__ == "__main__":
    control, candidate = sys.argv[1:]
    with TemporaryDirectory(prefix="relay-flags-") as tmp:
        source = Path(tmp, "bench.rs")
        exe = source.with_suffix(".exe")
        source.write_text("\n".join((get(control, "old_collector"), get(candidate, "new_collector"), FIXTURE)), encoding="utf-8")
        subprocess.run(["rustc", "--edition=2024", "-O", str(source), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
