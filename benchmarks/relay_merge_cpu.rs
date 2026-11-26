//! Build with rustc --edition 2024 -O, with --test for the renderer's parity tests.
#[path = "../crates/victory-gpu/src/shadow/relay_merge_simd.rs"]
mod relay_merge_simd;

// The production module uses the renderer clock only in its alternating
// mode. This CPU benchmark selects a fixed mode for each measured call.
mod host {
    pub(crate) fn now_ms() -> u64 {
        0
    }
}

mod bench_trial {
    use std::sync::atomic::{AtomicBool, Ordering};

    pub(crate) static SKIP: AtomicBool = AtomicBool::new(true);
    pub(crate) fn skip_equal(_: usize) -> bool {
        SKIP.load(Ordering::Relaxed)
    }
}

#[cfg(not(test))]
fn main() {
    use std::hint::black_box;
    use std::sync::atomic::Ordering;
    use std::time::{Duration, Instant};

    #[cfg(target_arch = "x86_64")]
    assert!(
        std::is_x86_feature_detected!("avx2"),
        "this comparison needs AVX2"
    );
    #[cfg(not(target_arch = "x86_64"))]
    panic!("this comparison needs x86-64 with AVX2");

    assert!(relay_merge_simd::enabled(), "enable VICTORY_RELAY_AVX2");
    const BYTES: usize = 4 << 20;
    for (pattern, step) in [
        ("equal", None),
        ("one byte per 4 KiB", Some(4096)),
        ("every other byte", Some(2)),
    ] {
        let before = vec![0x11; BYTES];
        let mut gpu = before.clone();
        if let Some(step) = step {
            for byte in gpu.iter_mut().step_by(step) {
                *byte = 0x77;
            }
        }
        // CPU writes differ from both the old snapshot and the GPU bytes.
        let initial_title = vec![0x55; BYTES];
        let mut expected = initial_title.clone();
        for ((title, &new), &old) in expected.iter_mut().zip(&gpu).zip(&before) {
            if new != old {
                *title = new;
            }
        }
        let mut held = before.clone();
        let mut title = initial_title.clone();
        let mut times = [Vec::new(), Vec::new()];
        for pair in 0..13 {
            for skip in [pair % 2 == 0, pair % 2 != 0] {
                held.copy_from_slice(&before);
                title.copy_from_slice(&initial_title);
                bench_trial::SKIP.store(skip, Ordering::Relaxed);
                let start = Instant::now();
                let changed = relay_merge_simd::merge(black_box(&gpu), &mut held, &mut title);
                let elapsed = start.elapsed();
                assert_eq!(changed, step.is_some());
                assert_eq!(held, gpu);
                assert_eq!(title, expected);
                if pair > 0 {
                    times[usize::from(skip)].push(elapsed);
                }
            }
        }
        let medians = times.map(|mut samples: Vec<Duration>| {
            samples.sort_unstable();
            (samples[5] + samples[6]).as_secs_f64() * 500_000.0
        });
        println!(
            "{pattern}: all vectors {:.1} us, skip equal vectors {:.1} us",
            medians[0], medians[1]
        );
    }
}
