//! Counts unchanged chunks in sampled CPU refreshes of already initialized
//! card-buffer staging memory. The subsequent refresh still copies all bytes.
use std::cell::{Cell, RefCell};
use std::sync::{Mutex, OnceLock};

const PERIOD: u32 = 67;
const BLOCK: usize = 64 * 1024;

/// A coarse write discards this history; the next exact observation starts
/// with that coarse generation as its floor.
pub(super) struct PageWrites {
    floor: u64,
    last: [u64; 16],
}

impl PageWrites {
    pub(super) fn new(floor: u64) -> Self {
        Self {
            floor,
            last: [0; 16],
        }
    }
    pub(super) fn record(&mut self, index: usize, now: u64) {
        self.last[index] = self.last[index].max(now);
    }
    pub(super) fn since(&self, copied: u64) -> Option<u16> {
        (copied >= self.floor).then(|| {
            self.last.iter().enumerate().fold(0, |bits, (index, &seq)| {
                bits | (u16::from(seq > copied) << index)
            })
        })
    }
}

pub(super) fn journal_enabled() -> bool {
    static ON: OnceLock<bool> = OnceLock::new();
    *ON.get_or_init(|| std::env::var_os("VICTORY_COPY_JOURNAL_AUDIT").is_some_and(|v| v == "1"))
}

thread_local! {
    static SEQUENCE: Cell<u32> = const { Cell::new(0) };
    static BUFFER: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
}

pub(super) fn selected() -> bool {
    static ENABLED: OnceLock<bool> = OnceLock::new();
    *ENABLED.get_or_init(|| std::env::var_os("VICTORY_COPY_AUDIT").is_some_and(|v| v == "1"))
        && SEQUENCE.with(|seq| {
            let n = (seq.get() + 1) % PERIOD;
            seq.set(n);
            n == 0
        })
}

fn changed_bytes(offset: usize, current: &[u8], previous: &[u8], chunk: usize) -> usize {
    let mut at = 0;
    let mut changed = 0;
    while at < current.len() {
        let next = current.len().min(at + chunk - ((offset + at) % chunk));
        if current[at..next] != previous[at..next] {
            changed += next - at;
        }
        at = next;
    }
    changed
}

fn checked_prediction(offset: usize, current: &[u8], held: &[u8], mask: u16) -> (usize, usize) {
    let (mut predicted, mut missed, mut at) = (0, 0, 0);
    while at < current.len() {
        let index = (offset + at) / 4096;
        let next = current.len().min((index + 1) * 4096 - offset);
        if mask & (1 << index) != 0 {
            predicted += next - at;
        } else if current[at..next] != held[at..next] {
            missed += next - at;
        }
        at = next;
    }
    (predicted, missed)
}

#[derive(Default)]
struct Counts {
    samples: usize,
    failed: usize,
    total: usize,
    changed_4k: usize,
    changed_16k: usize,
    changed_64k: usize,
    known: usize,
    predicted: usize,
    missed: usize,
}

/// Samples at most one journal page, possibly clipped to a view on either end.
pub(super) fn observe(address: usize, previous: &[u8], copied: u64, write: u64) {
    static COUNTS: Mutex<Counts> = Mutex::new(Counts {
        samples: 0,
        failed: 0,
        total: 0,
        changed_4k: 0,
        changed_16k: 0,
        changed_64k: 0,
        known: 0,
        predicted: 0,
        missed: 0,
    });
    let changed = BUFFER.with_borrow_mut(|buf| {
        buf.resize(previous.len(), 0);
        crate::host::read_into(address as *const u8, buf).then(|| {
            let chunks = [4096, 16384, BLOCK]
                .map(|chunk| changed_bytes(address % BLOCK, buf, previous, chunk));
            let prediction = journal_enabled()
                .then(|| crate::watch::observed_kernel_mask(address / BLOCK, copied, write))
                .flatten()
                .map(|mask| checked_prediction(address % BLOCK, buf, previous, mask));
            (chunks, prediction)
        })
    });
    let mut c = COUNTS.lock().unwrap_or_else(|e| e.into_inner());
    c.samples += 1;
    if let Some(([small, medium, whole], prediction)) = changed {
        if let Some((predicted, missed)) = prediction {
            c.known += previous.len();
            c.predicted += predicted;
            c.missed += missed;
        }
        c.total += previous.len();
        c.changed_4k += small;
        c.changed_16k += medium;
        c.changed_64k += whole;
    } else {
        c.failed += 1;
    }
    if c.samples == 128 {
        let c = std::mem::take(&mut *c);
        tracing::info!(target: "victory_copy_audit", samples=c.samples, failed=c.failed, bytes=c.total,
            changed_4k=c.changed_4k, changed_16k=c.changed_16k, changed_64k=c.changed_64k, known=c.known, predicted=c.predicted, missed=c.missed,
            "previously copied card-buffer bytes by changed chunk size");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newer_exact_writes_only_apply_after_the_last_coarse_write() {
        let mut writes = PageWrites::new(8);
        writes.record(0, 10);
        writes.record(15, 12);
        writes.record(15, 11);
        assert_eq!(writes.since(7), None);
        assert_eq!(writes.since(8), Some(0x8001));
        assert_eq!(writes.since(10), Some(0x8000));
        assert_eq!(writes.since(12), Some(0));
    }

    #[test]
    fn missing_changed_parts_are_counted_without_exposing_bytes() {
        let held = [0; 4106];
        let mut current = held;
        current[5] = 1;
        current[6] = 2;
        assert_eq!(checked_prediction(4090, &current, &held, 1 << 1), (4096, 6));
    }

    #[test]
    fn clips_changed_chunks_to_a_non_aligned_view() {
        let previous = [0; 9000];
        let mut current = previous;
        assert_eq!(changed_bytes(4090, &current, &previous, 4096), 0);
        current[5] = 1;
        current[6] = 2;
        current[8999] = 3;
        assert_eq!(
            changed_bytes(4090, &current, &previous, 4096),
            6 + 4096 + 802
        );
        assert_eq!(changed_bytes(4090, &current, &previous, 16384), 9000);
    }
}
