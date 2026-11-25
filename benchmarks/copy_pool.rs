mod before {
    use std::sync::{Arc, Mutex};
    include!("before.rs");
}
mod after {
    use std::sync::{Arc, Mutex, atomic::Ordering};
    include!("after.rs");
}

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Barrier};
type Work = fn(Vec<Box<dyn FnOnce() + Send>>);
fn batch(f: Work, n: usize, groups: usize, mixed: bool) {
    let mut buffers: Vec<_> = (0..n)
        .map(|j| {
            Some(vec![
                (j % 251) as u8;
                if mixed { 1024 + (j % 16) * 257 } else { 0 }
            ])
        })
        .collect();
    for _ in 0..groups {
        let count = Arc::new(AtomicUsize::new(0));
        let jobs = buffers
            .iter_mut()
            .enumerate()
            .map(|(i, b)| {
                let count = count.clone();
                let mut buf = b.take().unwrap();
                Box::new(move || {
                    for x in buf.iter_mut() {
                        *x = x.wrapping_add((i as u8) | 1);
                    }
                    std::hint::black_box(&buf);
                    count.fetch_add(1, Ordering::Relaxed);
                }) as Box<dyn FnOnce() + Send>
            })
            .collect();
        f(jobs);
        assert_eq!(count.load(Ordering::Relaxed), n);
        for (j, b) in buffers.iter_mut().enumerate() {
            *b = Some(vec![3; if mixed { 1024 + (j % 16) * 257 } else { 0 }]);
        }
    }
}
fn bench(f: Work, n: usize, clients: usize, mixed: bool) -> u128 {
    let barrier = Arc::new(Barrier::new(clients + 1));
    std::thread::scope(|s| {
        let mut ts = Vec::new();
        for _ in 0..clients {
            let b = barrier.clone();
            ts.push(s.spawn(move || {
                b.wait();
                batch(f, n, 64, mixed)
            }));
        }
        let start = std::time::Instant::now();
        barrier.wait();
        for t in ts {
            t.join().unwrap();
        }
        start.elapsed().as_micros()
    })
}
fn main() {
    for (n, clients, mixed) in [(64, 1, false), (512, 2, false), (128, 2, true)] {
        for pair in 0..9 {
            for flag in if pair % 2 == 0 {
                [false, true]
            } else {
                [true, false]
            } {
                let f: Work = if flag {
                    after::wide_run
                } else {
                    before::wide_run
                };
                let us = bench(f, n, clients, mixed);
                if pair > 0 {
                    println!("{n} {clients} {mixed} {pair} {flag} {us}");
                }
            }
        }
    }
}
