use std::collections::HashSet;
use std::hash::{BuildHasher, BuildHasherDefault, RandomState};
use std::hint::black_box;
use std::time::Instant;

type Range = (usize, usize, usize);

fn gather<H: BuildHasher + Default>(keys: &[Range]) -> (usize, usize) {
    let mut seen = HashSet::<Range, H>::default();
    let mut bytes = 0;
    for &(copy, lo, hi) in keys {
        if !seen.contains(&(copy, lo, hi)) {
            seen.insert((copy, lo, hi));
            bytes += hi - lo;
        }
    }
    (seen.len(), bytes)
}

fn measure<H: BuildHasher + Default>(keys: &[Range], runs: usize) -> f64 {
    let started = Instant::now();
    for _ in 0..runs {
        black_box(gather::<H>(black_box(keys)));
    }
    started.elapsed().as_nanos() as f64 / runs as f64
}

fn main() {
    type RendererHash = BuildHasherDefault<AddressHash>;
    println!("ranges,repeated,pair,random_ns,renderer_ns");
    for n in [64, 512, 4096] {
        for repeated in [false, true] {
            let keys: Vec<_> = (0..n)
                .map(|i| {
                    let index = if repeated { i / 3 } else { i };
                    let copy = 0x2_0000 + (index % 19) * 64;
                    let piece = index / 19 * 65536;
                    let lo = piece + (index % 17) * 16;
                    let hi = piece + 65536 - (index % 13) * 8;
                    (copy, lo, hi)
                })
                .collect();
            assert_eq!(gather::<RandomState>(&keys), gather::<RendererHash>(&keys));
            let runs = 480_000 / n;
            for pair in 0..7 {
                let (control, candidate) = if pair % 2 == 0 {
                    (
                        measure::<RandomState>(&keys, runs),
                        measure::<RendererHash>(&keys, runs),
                    )
                } else {
                    let candidate = measure::<RendererHash>(&keys, runs);
                    (measure::<RandomState>(&keys, runs), candidate)
                };
                println!("{n},{repeated},{pair},{control:.3},{candidate:.3}");
            }
        }
    }
}
