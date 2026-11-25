//! Local measurements for comparing runs with matching scene and resolution.

use std::cell::Cell;
use std::collections::HashMap;
use std::panic::Location;
use std::sync::{LazyLock, Mutex, OnceLock};
use std::time::{Duration, Instant};

#[derive(Default)]
struct Site {
    count: u64,
    bytes: u64,
    elapsed: Duration,
}

static READS: LazyLock<Mutex<HashMap<(&'static str, u32), Site>>> = LazyLock::new(Default::default);
static VIEWPORTS: LazyLock<Mutex<HashMap<(u32, u32), u64>>> = LazyLock::new(Default::default);
thread_local! {
    static READ_SEQUENCE: Cell<u32> = const { Cell::new(0) };
    static VIEW_SEQUENCE: Cell<u32> = const { Cell::new(0) };
}

fn enabled() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("VICTORY_BENCH_READS").is_some_and(|v| v == "1"))
}

fn sample(counter: &Cell<u32>, period: u32) -> bool {
    let n = counter.get().wrapping_add(1);
    counter.set(n);
    n.is_multiple_of(period)
}

pub(crate) struct ReadSample {
    caller: &'static Location<'static>,
    bytes: usize,
    start: Instant,
}

#[track_caller]
pub(crate) fn read(bytes: usize) -> Option<ReadSample> {
    if enabled() && READ_SEQUENCE.with(|c| sample(c, 67)) {
        Some(ReadSample {
            caller: Location::caller(),
            bytes,
            start: Instant::now(),
        })
    } else {
        None
    }
}

impl Drop for ReadSample {
    fn drop(&mut self) {
        let elapsed = self.start.elapsed();
        let mut reads = READS.lock().unwrap();
        let entry = reads
            .entry((self.caller.file(), self.caller.line()))
            .or_default();
        entry.count += 1;
        entry.bytes += self.bytes as u64;
        entry.elapsed += elapsed;
    }
}

pub(crate) fn viewport(w: u32, h: u32) {
    if enabled() && VIEW_SEQUENCE.with(|c| sample(c, 257)) {
        *VIEWPORTS.lock().unwrap().entry((w, h)).or_default() += 1;
    }
}

pub(crate) fn report() {
    if !enabled() {
        return;
    }
    static LAST: LazyLock<Mutex<Instant>> = LazyLock::new(|| Mutex::new(Instant::now()));
    let mut last = LAST.lock().unwrap();
    if last.elapsed() < Duration::from_secs(10) {
        return;
    }
    *last = Instant::now();
    let mut reads: Vec<_> = READS.lock().unwrap().drain().collect();
    reads.sort_unstable_by_key(|row| std::cmp::Reverse(row.1.elapsed));
    for ((file, line), site) in reads.iter().take(8) {
        tracing::info!(target: "victory_bench_reads", file, line, calls = site.count, bytes = site.bytes, us = site.elapsed.as_micros() as u64, "sampled reads");
    }
    let mut sizes: Vec<_> = VIEWPORTS.lock().unwrap().drain().collect();
    sizes.sort_unstable_by_key(|row| std::cmp::Reverse(row.1));
    for ((width, height), samples) in sizes.iter().take(6) {
        tracing::info!(target: "victory_bench_reads", width, height, samples, "sampled viewports");
    }
}
