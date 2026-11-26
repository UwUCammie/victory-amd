use std::hint::black_box;
use std::time::{Duration, Instant};

// MEASURED_SOURCE

// Compute the union independently in a byte map, including empty and reversed ranges.
fn check(input: &[(usize, usize)], merged: &[(usize, usize)]) {
    let mut map = vec![false; 16_384];
    for &(a, b) in input {
        if a < b { map[a..b].fill(true); }
    }
    let mut seen = vec![false; map.len()];
    let mut end = None;
    for &(a, b) in merged {
        assert!(a < b && end.is_none_or(|last| last < a));
        seen[a..b].fill(true);
        end = Some(b);
    }
    assert_eq!(map, seen);
}

fn sample(count: usize, dispersed: bool) -> u128 {
    let mut state = 17u32;
    let mut total = Duration::ZERO;
    let mut rounds: u32 = 0;
    for seed in 0..48 {
        let mut input = Vec::new();
        for i in 0..count {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            let a = (state >> 16) as usize % if dispersed { 16_000 } else { 512 };
            let b = if i % 13 == 0 { a.saturating_sub(1) } else { a + ((state >> 9) as usize % 96) };
            input.push((a, b));
        }
        // Include existing ranges on the second call, as the submitter does.
        let split = input.len() / 2;
        let mut ranges = Vec::new();
        join_ranges(&mut ranges, input[..split].iter().copied());
        join_ranges(&mut ranges, input[split..].iter().copied());
        check(&input, &ranges);
        let repeats = 1600 / count.max(1) + 32;
        let start = Instant::now();
        for _ in 0..repeats {
            let mut ranges = Vec::new();
            join_ranges(&mut ranges, black_box(&input[..split]).iter().copied());
            join_ranges(&mut ranges, black_box(&input[split..]).iter().copied());
            black_box(ranges);
        }
        if seed > 0 {
            total += start.elapsed();
            rounds += repeats as u32;
        }
    }
    total.as_nanos() / u128::from(rounds)
}

fn main() {
    for n in [0, 4, 16, 64, 256] {
        for dispersed in [false, true] {
            let label = if dispersed { "dispersed" } else { "clustered" };
            println!("{label}-{n} {}", sample(n, dispersed));
        }
    }
}
