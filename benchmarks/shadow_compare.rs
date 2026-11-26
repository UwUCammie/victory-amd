//! Compare the two byte comparisons used by find_pieces on synthetic buffers.
use std::hint::black_box;
use std::time::Instant;

// MEASURED_SOURCE

#[inline(never)]
fn changed(vector: bool, a: &[u8], b: &[u8]) -> bool {
    assert_eq!(a.len(), b.len());
    if vector {
        // SAFETY: both slices cover the supplied length; main checks AVX2.
        unsafe { differ(a.as_ptr(), b.as_ptr(), a.len()) }
    } else {
        a != b
    }
}

fn main() {
    assert!(std::is_x86_feature_detected!("avx2"));
    let mut second = vec![19u8; 65_545];
    let first = vec![19u8; second.len()];
    for n in [0usize, 1, 15, 31, 32, 33, 127, 128, 129, 255, 256, 65_536] {
        for offset in 0..4 {
            for i in [None, Some(0), n.checked_sub(1)] {
                if let Some(i) = i.filter(|&i| i < n) { second[offset + i] ^= 2; }
                let a = &first[offset..offset+n];
                let b = &second[offset..offset+n];
                assert_eq!(changed(true, a, b), changed(false, a, b));
                if let Some(i) = i.filter(|&i| i < n) { second[offset + i] ^= 2; }
            }
        }
    }
    let block = 65_536;
    let blocks = 128;
    let a = vec![53u8; block * blocks + 5];
    let mut b = a.clone();
    for (case, offset) in [("equal", None), ("first", Some(0)), ("middle", Some(block/2)), ("last", Some(block-1))] {
        if let Some(offset) = offset {
            for i in 0..blocks { b[3 + i * block + offset] ^= 1; }
        }
        for pair in 0..9 {
            for mode in 0..2 {
                let vector = (mode + pair) % 2 == 1;
                let timer = Instant::now();
                let mut count = 0;
                for _ in 0..16 {
                    for i in 0..blocks {
                        let p = 3 + i * block;
                        count += changed(black_box(vector), black_box(&a[p..p+block]), black_box(&b[p..p+block])) as usize;
                    }
                }
                let ns = timer.elapsed().as_nanos() / (16 * blocks) as u128;
                assert_eq!(count, if offset.is_some() { 16 * blocks } else { 0 });
                if pair != 0 { println!("{case} {pair} {} {ns}", if vector { "avx2" } else { "slice" }); }
            }
        }
        if let Some(offset) = offset {
            for i in 0..blocks { b[3 + i * block + offset] ^= 1; }
        }
    }
}
