use std::collections::{HashMap, hash_map::RandomState};
use std::hash::{BuildHasher, BuildHasherDefault};
use std::hint::black_box;
use std::time::Instant;

type Key = (usize, u64);

fn work<S: BuildHasher + Default>(keys: &[Key], touches: &[usize], lists: usize) -> (u128, usize) {
    let mut slots = HashMap::<Key, usize, S>::with_capacity_and_hasher(keys.len(), S::default());
    let before = Instant::now();
    let mut check = 0usize;
    for _ in 0..lists {
        slots.clear();
        for &index in touches {
            let key = black_box(keys[index]);
            let slot = match slots.get(&key) {
                Some(&slot) => slot,
                None => {
                    let slot = slots.len();
                    slots.insert(key, slot);
                    slot
                }
            };
            check = check.wrapping_add(black_box(slot));
        }
    }
    (before.elapsed().as_nanos(), check)
}

fn main() {
    let sizes = [32, 256, 2048];
    for n in sizes {
        // 256-byte aligned root addresses, several heaps, and separate biased
        // and ordinary slots, as in root_srv_table.
        let keys: Vec<Key> = (0..n)
            .map(|i| {
                let heap = 0x0010_0000 + (i % 5) * 0x100;
                let address = 0x8000_0000 + ((i as u64 / 2) << 8);
                let bias = ((i % 2) as u64) << 63;
                (heap, address | bias)
            })
            .collect();
        let touches: Vec<usize> = (0..n * 8)
            .map(|i| i.wrapping_mul(17).wrapping_add(i / n) % n)
            .collect();
        let lists = 1_048_576 / touches.len();
        for pair in 0..7 {
            let original;
            let candidate;
            if pair % 2 == 0 {
                original = work::<RandomState>(&keys, &touches, lists);
                candidate = work::<BuildHasherDefault<AddressHash>>(&keys, &touches, lists);
            } else {
                candidate = work::<BuildHasherDefault<AddressHash>>(&keys, &touches, lists);
                original = work::<RandomState>(&keys, &touches, lists);
            }
            assert_eq!(original.1, candidate.1);
            println!("{n},{pair},{},{}", original.0 / lists as u128, candidate.0 / lists as u128);
        }
    }
}
