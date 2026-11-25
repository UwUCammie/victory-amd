//! Counts unchanged chunks in sampled CPU refreshes of already initialized
//! card-buffer staging memory. The subsequent refresh still copies all bytes.
use std::cell::{Cell, RefCell};
use std::sync::{Mutex, OnceLock};

const PERIOD: u32 = 67;
const BLOCK: usize = 64 * 1024;

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

#[derive(Default)]
struct Counts {
    samples: usize,
    failed: usize,
    total: usize,
    changed_4k: usize,
    changed_16k: usize,
    changed_64k: usize,
}

/// Samples at most one journal page, possibly clipped to a view on either end.
pub(super) fn observe(address: usize, previous: &[u8]) {
    static COUNTS: Mutex<Counts> = Mutex::new(Counts {
        samples: 0,
        failed: 0,
        total: 0,
        changed_4k: 0,
        changed_16k: 0,
        changed_64k: 0,
    });
    let changed = BUFFER.with_borrow_mut(|buf| {
        buf.resize(previous.len(), 0);
        crate::host::read_into(address as *const u8, buf).then(|| {
            [4096, 16384, BLOCK].map(|chunk| changed_bytes(address % BLOCK, buf, previous, chunk))
        })
    });
    let mut c = COUNTS.lock().unwrap_or_else(|e| e.into_inner());
    c.samples += 1;
    if let Some([small, medium, whole]) = changed {
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
            changed_4k=c.changed_4k, changed_16k=c.changed_16k, changed_64k=c.changed_64k,
            "previously copied card-buffer bytes by changed chunk size");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
