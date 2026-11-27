use std::collections::BTreeMap;
use std::hint::black_box;
use std::time::Instant;

type Range = (usize, usize);

fn scan(ranges: &[Range]) -> Vec<Range> {
    let mut due = Vec::new();
    for &(first, last) in ranges {
        if !due.iter().any(|&(start, end)| start <= first && last <= end) {
            due.push((first, last));
        }
    }
    due
}

#[cfg(adaptive)]
fn index(ranges: &[Range]) -> Vec<Range> {
    let mut rest = RestRanges::default();
    for (i, &(first, last)) in ranges.iter().enumerate() {
        rest.note(first, last, ranges.len() - i);
    }
    rest.requests
}

#[cfg(not(adaptive))]
fn index(ranges: &[Range]) -> Vec<Range> {
    let mut earlier = BTreeMap::new();
    ranges.iter().copied().filter(|&(first, last)| record_uncovered(&mut earlier, first, last)).collect()
}

fn samples(case: &str, size: usize, seed: u64) -> Vec<Range> {
    let mut state = seed;
    let mut random = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state as usize
    };
    let mut ranges: Vec<_> = match case {
        "sorted" | "shuffled" => (0..size).map(|n| (4 * n, 4 * n + 2)).collect(),
        "nested" => (0..size).map(|n| (n, 2 * size - n)).collect(),
        "mixed" => (0..size).map(|_| {
            let first = random() % (2 * size);
            (first, first + 1 + random() % 32)
        }).collect(),
        _ => unreachable!(),
    };
    if case == "shuffled" {
        for i in (1..ranges.len()).rev() {
            ranges.swap(i, random() % (i + 1));
        }
    }
    ranges
}

fn time(select: fn(&[Range]) -> Vec<Range>, ranges: &[Range]) -> u128 {
    let repeats = (4096 / ranges.len()).max(1);
    let start = Instant::now();
    for _ in 0..repeats {
        black_box(select(black_box(ranges)));
    }
    start.elapsed().as_nanos() / repeats as u128
}

fn main() {
    for seed in 1..=400 {
        let ranges = samples("mixed", 17 + seed as usize * 13 % 770, seed);
        assert_eq!(scan(&ranges), index(&ranges), "generated sequence {seed}");
    }
    println!("Generated mixed inputs agree in order and contents across 400 seeds");
    for size in [16, 64, 256, 512, 1024, 4096] {
        for case in ["sorted", "shuffled", "nested", "mixed"] {
            let ranges = samples(case, size, 14951);
            let requests = scan(&ranges);
            assert_eq!(requests, index(&ranges));
            for pair in 0..9 {
                let (a, b) = if pair % 2 == 0 {
                    (time(scan, &ranges), time(index, &ranges))
                } else {
                    let b = time(index, &ranges);
                    (time(scan, &ranges), b)
                };
                if pair > 0 {
                    println!("{case},{size},{},{a},{b}", requests.len());
                }
            }
        }
    }
}
