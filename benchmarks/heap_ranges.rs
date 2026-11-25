//! Synthetic descriptor-slot and shadow-span benchmark on the host CPU.
//! Run with rustc --edition=2024 -O benchmarks/heap_ranges.rs, then ./heap_ranges.
//! The integer hasher comes from Marvisak/VIctory pull request 2102.
#[path = "../crates/victory-gpu/src/fx.rs"]
#[allow(dead_code)]
mod fx;

use std::{
    collections::{HashMap, hash_map::Entry},
    hash::BuildHasher,
    sync::Arc,
    time::Instant,
};
#[derive(Clone)]
struct Span(Arc<u64>, u64, u64);
fn measure<H: BuildHasher + Default>(single: bool) -> (u128, u64) {
    let resources: Vec<_> = (0..4600).map(Arc::new).collect();
    let mut slots: HashMap<u32, Span, H> = HashMap::default();
    let started = Instant::now();
    let mut check = 0;
    for frame in 0u32..24 {
        slots.retain(|k, _| (k % 16) != (frame % 16));
        for j in 0..43000u32 {
            let slot = (j * 173 + frame * 6257) % 82000;
            let id = ((slot.wrapping_mul(19) + frame * 3) % 4600) as usize;
            let shadow = &resources[id];
            let start = u64::from(slot % 530) * 128;
            let end = start + 1024;
            if single {
                match slots.entry(slot) {
                    Entry::Occupied(mut o) => {
                        let v = o.get_mut();
                        if !Arc::ptr_eq(&v.0, shadow) || v.1 != start || v.2 != end {
                            *v = Span(shadow.clone(), start, end);
                        }
                    }
                    Entry::Vacant(v) => {
                        v.insert(Span(shadow.clone(), start, end));
                    }
                }
            } else if let Some(v) = slots.get_mut(&slot) {
                if !Arc::ptr_eq(&v.0, shadow) || v.1 != start || v.2 != end {
                    *v = Span(shadow.clone(), start, end);
                }
            } else {
                slots.insert(slot, Span(shadow.clone(), start, end));
            }
        }
        let mut spans: HashMap<usize, Span, H> =
            HashMap::with_capacity_and_hasher(slots.len().min(8192), H::default());
        for Span(shadow, lo, hi) in slots.values() {
            let key = Arc::as_ptr(shadow) as usize;
            let v = spans
                .entry(key)
                .or_insert_with(|| Span(shadow.clone(), *lo, *hi));
            v.1 = v.1.min(*lo);
            v.2 = v.2.max(*hi);
        }
        check += spans.values().map(|v| v.2 - v.1 + *v.0).sum::<u64>();
        std::hint::black_box(&spans);
    }
    (started.elapsed().as_micros(), check)
}
fn main() {
    let mut answer = None;
    for i in 0..9 {
        for fast in if i % 2 == 0 {
            [false, true]
        } else {
            [true, false]
        } {
            let (us, n) = if fast {
                measure::<std::hash::BuildHasherDefault<fx::Fx>>(true)
            } else {
                measure::<std::hash::RandomState>(false)
            };
            if let Some(want) = answer {
                assert_eq!(n, want)
            } else {
                answer = Some(n)
            }
            if i > 0 {
                println!("{i} {fast} {us} {n}")
            }
        }
    }
}
