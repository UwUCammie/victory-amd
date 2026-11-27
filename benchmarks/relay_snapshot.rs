use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
use std::time::Instant;

struct Count;
static ALLOCS: AtomicUsize = AtomicUsize::new(0);

#[global_allocator]
static ALLOCATOR: Count = Count;

unsafe impl GlobalAlloc for Count {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, old: Layout, new_size: usize) -> *mut u8 {
        ALLOCS.fetch_add(1, Relaxed);
        unsafe { System.realloc(ptr, old, new_size) }
    }
}

fn trial(input: &[Vec<u8>], reused: bool, rounds: usize) -> (usize, f64, usize) {
    let mut checksum = 0usize;
    let before = ALLOCS.load(Relaxed);
    let start = Instant::now();
    for _ in 0..rounds {
        let mut scratch = Vec::new();
        for title in input {
            if reused {
                scratch.clone_from(black_box(title));
                checksum += usize::from(*black_box(&scratch)[title.len() - 1..].first().unwrap());
            } else {
                let snapshot = black_box(title).clone();
                checksum += usize::from(*black_box(&snapshot)[title.len() - 1..].first().unwrap());
            }
        }
    }
    (
        ALLOCS.load(Relaxed) - before,
        start.elapsed().as_nanos() as f64 / (rounds * input.len()) as f64,
        checksum,
    )
}

fn main() {
    let input: Vec<_> = (0..64)
        .map(|i| {
            let n = (1 + i % 4) * 4096;
            (0..n).map(|j| (i + j * 3) as u8).collect::<Vec<_>>()
        })
        .collect();
    let mut scratch = Vec::new();
    for title in &input {
        scratch.clone_from(title);
        assert_eq!(&scratch, title);
    }
    println!(
        "pair,control_allocs,candidate_allocs,control_ns_per_snapshot,candidate_ns_per_snapshot"
    );
    for pair in 0..11 {
        let (a, b) = if pair % 2 == 0 {
            (trial(&input, false, 100), trial(&input, true, 100))
        } else {
            let b = trial(&input, true, 100);
            (trial(&input, false, 100), b)
        };
        assert_eq!(a.2, b.2);
        println!("{pair},{},{},{:.3},{:.3}", a.0, b.0, a.1, b.1);
    }
}
