use std::hint::black_box;
use std::time::Instant;

type Merge = fn(&[u8], &mut [u8], &mut [u8]) -> bool;

fn measure(merge: Merge, old: &[u8], new: &[u8], shown: &[u8], repeats: usize) -> f64 {
    let mut held = old.to_vec();
    let mut title = shown.to_vec();
    let started = Instant::now();
    for iteration in 0..repeats {
        let now = if iteration % 2 == 0 { new } else { old };
        black_box(merge(
            black_box(now),
            black_box(&mut held),
            black_box(&mut title),
        ));
    }
    started.elapsed().as_nanos() as f64 / repeats as f64
}

fn transition(merge: Merge, old: &[u8], new: &[u8], shown: &[u8]) -> (bool, Vec<u8>, Vec<u8>) {
    let mut held = old.to_vec();
    let mut title = shown.to_vec();
    let changed = merge(new, &mut held, &mut title);
    (changed, held, title)
}

fn main() {
    println!("bytes,changes,pair,control_ns,candidate_ns");
    for bytes in [31usize, 511, 65_536] {
        let raw: Vec<u8> = (0..=bytes)
            .map(|i| (i.wrapping_mul(93usize) >> 1) as u8)
            .collect();
        let old = &raw[1..];
        let mut shown = old.to_vec();
        for value in shown.iter_mut().skip(1).step_by(7) {
            *value ^= 0x80;
        }
        for (name, stride) in [("equal", 0), ("sparse", 113), ("dense", 1)] {
            let mut new = old.to_vec();
            if stride != 0 {
                for value in new.iter_mut().step_by(stride) {
                    *value ^= 0x5b;
                }
            }
            assert_eq!(
                transition(control, old, &new, &shown),
                transition(candidate, old, &new, &shown)
            );
            let repeats = (5_000_000 / bytes).max(100);
            for pair in 0..7 {
                let left;
                let right;
                if pair % 2 == 0 {
                    left = measure(control, old, &new, &shown, repeats);
                    right = measure(candidate, old, &new, &shown, repeats);
                } else {
                    right = measure(candidate, old, &new, &shown, repeats);
                    left = measure(control, old, &new, &shown, repeats);
                }
                println!("{bytes},{name},{pair},{left:.3},{right:.3}");
            }
        }
    }
    // The shared length, including uneven inputs, is still the only prefix visited.
    for (old, new, title) in [
        (&[3, 1, 7][..], &[5, 2][..], &[6, 2, 4][..]),
        (&[3, 1][..], &[5, 2, 1][..], &[6, 2, 4][..]),
        (&[3, 1, 7][..], &[5, 2, 1][..], &[6][..]),
    ] {
        assert_eq!(
            transition(control, old, new, title),
            transition(candidate, old, new, title)
        );
    }
    for (old_len, new_len, title_len) in [(63, 64, 64), (64, 63, 64), (64, 64, 63), (97, 129, 131)]
    {
        let old = vec![3; old_len];
        let new = vec![5; new_len];
        let title = vec![6; title_len];
        assert_eq!(
            transition(control, &old, &new, &title),
            transition(candidate, &old, &new, &title)
        );
    }
}
