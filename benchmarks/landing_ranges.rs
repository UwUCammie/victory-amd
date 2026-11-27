use std::{hint::black_box, time::Instant};

type Span = (usize, usize);
const PIECE: usize = 65_536;

fn control(pieces: &[Span], skip: Vec<Span>, mut each: impl FnMut(&[Span])) {
    for &(lo, hi) in pieces {
        let near = skip
            .iter()
            .copied()
            .filter(|&(a, b)| a < hi && b > lo)
            .collect();
        let parts: Vec<_> = outside(lo, hi, near)
            .into_iter()
            .map(|(a, b)| (a - lo, b - lo))
            .collect();
        each(&parts);
    }
}

fn candidate(pieces: &[Span], mut skip: Vec<Span>, mut each: impl FnMut(&[Span])) {
    skip.sort_unstable();
    let mut parts = Vec::new();
    for &(lo, hi) in pieces {
        parts.clear();
        outside_sorted(lo, hi, &skip, |a, b| parts.push((a - lo, b - lo)));
        each(&parts);
    }
}

fn exclusions(count: usize, n: usize) -> Vec<Span> {
    (0..count)
        .rev()
        .map(|i| {
            let at = (i * 308_093 + 8192) % (n * PIECE);
            (at, at + ((i % 5) + 1) * 10_240)
        })
        .collect()
}

fn measure(pieces: &[Span], skip: &[Span], n: usize, new: bool) -> f64 {
    let begin = Instant::now();
    for _ in 0..n {
        let skip = black_box(skip).to_vec();
        let side = |parts: &[Span]| {
            black_box(parts);
        };
        if new {
            candidate(black_box(pieces), skip, side);
        } else {
            control(black_box(pieces), skip, side);
        }
    }
    begin.elapsed().as_nanos() as f64 / n as f64
}

fn main() {
    println!("pieces,exclusions,pair,control_ns,candidate_ns");
    for n in [1, 8, 64] {
        let pieces: Vec<_> = (0..n)
            .map(|i| (i * PIECE + 16, (i + 1) * PIECE - 4))
            .collect();
        for count in [0, n, n * 8] {
            let skip = exclusions(count, n);
            let mut before = Vec::new();
            let mut after = Vec::new();
            control(&pieces, skip.clone(), |parts| before.push(parts.to_vec()));
            candidate(&pieces, skip.clone(), |parts| after.push(parts.to_vec()));
            assert_eq!(before, after);
            let runs = 30_000 / n;
            for pair in 0..7 {
                let left;
                let right;
                if pair % 2 == 0 {
                    left = measure(&pieces, &skip, runs, false);
                    right = measure(&pieces, &skip, runs, true);
                } else {
                    right = measure(&pieces, &skip, runs, true);
                    left = measure(&pieces, &skip, runs, false);
                }
                println!("{n},{count},{pair},{left:.3},{right:.3}");
            }
        }
    }
}
