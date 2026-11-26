use std::hint::black_box;
use std::time::Instant;

fn run(scan: fn(&[u8], &[u8]) -> Option<usize>, a: &[u8], b: &[u8], n: usize) -> (f64, usize) {
    let mut sum = 0usize;
    let start = Instant::now();
    for _ in 0..n {
        sum = sum.wrapping_add(black_box(scan(black_box(a), black_box(b))).unwrap_or(a.len()));
    }
    (start.elapsed().as_nanos() as f64 / n as f64, sum)
}

fn main() {
    assert!(std::is_x86_feature_detected!("avx2"));
    println!("case,pair,control_ns,candidate_ns");
    for (name, bytes, change, n) in [
        ("identical_64k", 65_536, None, 12_000),
        ("different_near_start", 65_536, Some(17), 12_000),
        ("different_at_midpoint", 65_536, Some(32_768), 20_000),
        ("different_in_last_block", 65_536, Some(65_517), 750_000),
        ("different_in_tail", 65_539, Some(65_537), 750_000),
        ("single_block", 32, Some(23), 750_000),
    ] {
        let data: Vec<u8> = (0..bytes + 1).map(|i| (i as u32).wrapping_mul(507_391) as u8).collect();
        let a = &data[1..];
        let mut other = a.to_vec();
        if let Some(index) = change {
            other[index] ^= 0x80;
        }
        assert_eq!(control(a, &other), change);
        assert_eq!(candidate(a, &other), change);
        for pair in 0..7 {
            let (left, right) = if pair % 2 == 0 {
                (run(control, a, &other, n), run(candidate, a, &other, n))
            } else {
                let right = run(candidate, a, &other, n);
                (run(control, a, &other, n), right)
            };
            assert_eq!(left.1, right.1);
            println!("{name},{pair},{:.3},{:.3}", left.0, right.0);
        }
    }
}
