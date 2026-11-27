"""Compare renderer write-watch part updates for generated masks."""

from argparse import ArgumentParser
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
import subprocess

parser = ArgumentParser(description=__doc__)
parser.add_argument("checkout", type=Path)
parser.add_argument("--base", required=True, help="revision of the original update loop")
parser.add_argument("--scratch", type=Path)
args = parser.parse_args()
path = "crates/victory-gpu/src/watch.rs"
checkout = args.checkout


def source(text, name):
    start = text.index("\n", text.index("let all = self.parts.entry(page)")) + 1
    end = text.index("\n        before\n", start)
    return f"#[inline(never)] fn {name}(all: &mut [u64; 16], parts: u16, now: u64) {{\n{text[start:end]}\n}}"


old = subprocess.check_output(["git", "-C", str(checkout), "show", f"{args.base}:{path}"], text=True)
new = (checkout / path).read_text()
harness = """use std::hint::black_box;
use std::time::Instant;

fn time(set: fn(&mut [u64; 16], u16, u64), count: u32) -> u128 {
    let mask = ((1u32 << count) - 1) as u16;
    let mut generations = [0; 16];
    let start = Instant::now();
    for i in 0..300_000 {
        let offset = (i ^ (i / 16)) & 15;
        set(black_box(&mut generations), black_box(mask.rotate_left(offset)), black_box(i as u64 + 17));
    }
    black_box(generations);
    start.elapsed().as_nanos()
}

fn main() {
    for mask in 0..=u16::MAX {
        let mut a = std::array::from_fn(|i| i as u64);
        let mut b = a;
        old(&mut a, mask, 431);
        new(&mut b, mask, 431);
        assert_eq!(a, b, "mask {mask}");
    }
    println!("all 65536 masks agree");
    for count in [1, 2, 4, 8, 12, 15] {
        for pair in 0..13 {
            let (a, b) = if pair % 2 == 0 {
                (time(old, count), time(new, count))
            } else {
                let b = time(new, count);
                (time(old, count), b)
            };
            if pair > 0 {
                println!("{count},{a},{b}");
            }
        }
    }
}
"""
with TemporaryDirectory(dir=args.scratch) as scratch:
    source_file = Path(scratch) / "watch_parts.rs"
    source_file.write_text(source(old, "old") + "\n" + source(new, "new") + "\n" + harness, encoding="utf-8", newline="\n")
    for cpu in ("x86-64", "x86-64-v3"):
        exe = source_file.with_suffix("." + cpu)
        subprocess.run(["rustc", "--edition=2024", "-C", "opt-level=3", "-C", f"target-cpu={cpu}", str(source_file), "-o", str(exe)], check=True)
        lines = subprocess.check_output([str(exe)], text=True).splitlines()
        print(cpu, lines[0])
        groups = {}
        for row in lines[1:]:
            count, a, b = map(int, row.split(","))
            groups.setdefault(count, []).append((a, b))
        for count, samples in groups.items():
            a, b = zip(*samples)
            print(f"{count:2} parts  {median(a) / 300_000:.2f} -> {median(b) / 300_000:.2f} ns  "
                  f"{100 * (median(q/p for p, q in samples) - 1):+.2f}%")
