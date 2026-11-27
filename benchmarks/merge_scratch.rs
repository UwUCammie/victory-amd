use std::{hint::black_box, time::Instant};

type Read = fn(usize, &mut [u8]) -> bool;
type Merge = fn(
    &mut [u8],
    &[u8],
    &mut Vec<u8>,
    &mut Vec<u8>,
    &mut Vec<(usize, usize)>,
    Read,
) -> Option<(usize, usize)>;

fn read(_: usize, target: &mut [u8]) -> bool {
    target.fill(11);
    true
}

fn measure(merge: Merge, before: &[u8], after: &[u8], times: usize) -> f64 {
    let mut gpu = after.to_vec();
    let mut title = vec![0x23; before.len()];
    let mut mask = vec![0x54; before.len()];
    let mut runs = Vec::with_capacity(before.len());
    let start = Instant::now();
    for _ in 0..times {
        black_box(merge(
            black_box(&mut gpu),
            black_box(before),
            &mut title,
            &mut mask,
            &mut runs,
            read,
        ));
    }
    let elapsed = start.elapsed();
    assert_eq!(gpu, after);
    assert_eq!(title, after);
    let recovered: Vec<_> = runs.iter().flat_map(|(at, n)| *at..at + n).collect();
    let changed: Vec<_> = before
        .iter()
        .zip(after)
        .enumerate()
        .filter_map(|(at, (a, b))| (a != b).then_some(at))
        .collect();
    assert_eq!(recovered, changed);
    elapsed.as_nanos() as f64 / times as f64
}

fn main() {
    println!("bytes,density,pair,control_ns,candidate_ns");
    for size in [256usize, 4096, 65536] {
        let before = vec![11; size];
        for (kind, stride) in [("sparse", 521), ("dense", 1)] {
            let mut after = before.clone();
            for at in (0..size).step_by(stride) {
                after[at] = 19;
            }
            after[size - 1] = 19;
            let times = 9_000_000 / size;
            for pair in 0..7 {
                let a;
                let b;
                if pair % 2 == 0 {
                    a = measure(control, &before, &after, times);
                    b = measure(candidate, &before, &after, times);
                } else {
                    b = measure(candidate, &before, &after, times);
                    a = measure(control, &before, &after, times);
                }
                println!("{size},{kind},{pair},{a:.3},{b:.3}");
            }
        }
    }
}
