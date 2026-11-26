//! One-launch A/B measurement for renderer switches that preserve resource state.
use std::sync::OnceLock;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::Duration;

enum Mode {
    Fixed(bool),
    Paired,
}

#[derive(Clone, Copy)]
enum Case {
    MergeLanes,
    CardSync,
}

impl Case {
    fn mode(self) -> &'static Mode {
        static MERGE_LANES: OnceLock<Mode> = OnceLock::new();
        static CARD: OnceLock<Mode> = OnceLock::new();
        let (cell, key, default) = match self {
            Self::MergeLanes => (&MERGE_LANES, "VICTORY_MERGE_SKIP_EQUAL", false),
            Self::CardSync => (&CARD, "VICTORY_CARD_SYNC_BATCH", true),
        };
        cell.get_or_init(|| match std::env::var(key).as_deref() {
            Ok("paired") => Mode::Paired,
            Ok("0") => Mode::Fixed(false),
            Ok("1") => Mode::Fixed(true),
            _ => Mode::Fixed(default),
        })
    }
    fn enabled(self) -> bool {
        match self.mode() {
            Mode::Fixed(value) => *value,
            Mode::Paired => ENABLED.load(Ordering::Relaxed),
        }
    }
    fn count(self) -> u64 {
        match self {
            Self::MergeLanes => COMPARED_MIB[1].load(Ordering::Relaxed),
            Self::CardSync => BATCHED_BUFFERS.load(Ordering::Relaxed),
        }
    }
}
static ENABLED: AtomicBool = AtomicBool::new(false);
static BATCHED_BUFFERS: AtomicU64 = AtomicU64::new(0);

static COMPARED_MIB: [AtomicU64; 2] = [const { AtomicU64::new(0) }; 2];

#[cfg(target_arch = "x86_64")]
pub(crate) fn skip_equal(bytes: usize) -> bool {
    let enabled = Case::MergeLanes.enabled();
    if matches!(Case::MergeLanes.mode(), Mode::Paired) {
        // Count both modes with the same work in the relay merge. Publish whole
        // MiB per thread so workers do not share an atomic on every short slice.
        thread_local! { static PENDING: std::cell::Cell<[u64; 2]> = const { std::cell::Cell::new([0; 2]) }; }
        PENDING.with(|pending| {
            let mut counts = pending.get();
            let slot = usize::from(enabled);
            counts[slot] += bytes as u64;
            if counts[slot] >= 1 << 20 {
                COMPARED_MIB[slot].fetch_add(counts[slot] >> 20, Ordering::Relaxed);
                counts[slot] &= (1 << 20) - 1;
            }
            pending.set(counts);
        });
    }
    enabled
}
pub(crate) fn sync_batched() -> bool {
    Case::CardSync.enabled()
}
pub(crate) fn record_batch(size: usize) {
    if size > 1 && matches!(Case::CardSync.mode(), Mode::Paired) {
        BATCHED_BUFFERS.fetch_add(size as u64, Ordering::Relaxed);
    }
}

// Each four-block set balances a linear drift. A longer trial reverses the order.
const BLOCKS: [bool; 8] = [false, true, true, false, true, false, false, true];

pub(crate) struct Trial {
    case: Case,
    block: usize, // 0 is warm-up, 1 through 8 are measured
    duration: Duration,
    block_duration: Duration,
    elapsed: Duration,
    measured: Duration,
    frames: u64,
    draws: u64,
    skipped_before: u64,
}

impl Trial {
    pub(crate) fn from_env() -> Option<Self> {
        let case = match (Case::MergeLanes.mode(), Case::CardSync.mode()) {
            (Mode::Paired, Mode::Fixed(_)) => Case::MergeLanes,
            (Mode::Fixed(_), Mode::Paired) => Case::CardSync,
            (Mode::Paired, Mode::Paired) => {
                tracing::warn!("select only one paired renderer switch per benchmark");
                return None;
            }
            _ => return None,
        };
        fn seconds(key: &str, default: u64, min: u64) -> Duration {
            let value = std::env::var(key)
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default);
            Duration::from_secs(value.max(min))
        }
        let duration = seconds("VICTORY_BENCH_WARMUP_SECONDS", 150, 0);
        let block_duration = seconds("VICTORY_BENCH_BLOCK_SECONDS", 40, 5);
        Some(Self::new(case, duration, block_duration))
    }

    fn new(case: Case, duration: Duration, block_duration: Duration) -> Self {
        ENABLED.store(false, Ordering::Relaxed);
        Self {
            case,
            block: 0,
            duration,
            block_duration,
            elapsed: Duration::ZERO,
            measured: Duration::ZERO,
            frames: 0,
            draws: 0,
            skipped_before: 0,
        }
    }

    pub(crate) fn interval(&mut self, dt: Duration, frames: u32, draws: u64) {
        if self.block > BLOCKS.len() {
            return;
        }
        let skipped = self.case.count();
        if self.block > 0 {
            if self.elapsed.is_zero() {
                // Discard the first complete reporting interval after each boundary.
                self.skipped_before = skipped;
            } else {
                self.measured += dt;
                self.frames += u64::from(frames);
                self.draws += draws;
            }
        }
        self.elapsed += dt;
        if self.elapsed < self.duration {
            return;
        }
        if self.block > 0 {
            let label = match self.case {
                Case::MergeLanes => "merge_lanes",
                Case::CardSync => "card_sync",
            };
            tracing::info!(target: "victory_bench", kind = label, block = self.block,
                enabled = BLOCKS[self.block - 1], frames = self.frames,
                interval_us = self.measured.as_micros() as u64, draws = self.draws,
                work_units = skipped - self.skipped_before, block_s = self.block_duration.as_secs(),
                "renderer trial");
        }
        self.block += 1;
        ENABLED.store(
            BLOCKS.get(self.block - 1).copied().unwrap_or(false),
            Ordering::Relaxed,
        );
        self.duration = self.block_duration;
        self.elapsed = Duration::ZERO;
        self.measured = Duration::ZERO;
        self.frames = 0;
        self.draws = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn eight_blocks_share_one_warmup_and_each_drops_one_interval() {
        let sec = Duration::from_secs(1);
        let mut trial = Trial::new(Case::MergeLanes, 2 * sec, 3 * sec);
        trial.interval(sec, 99, 990);
        assert_eq!(trial.block, 0);
        trial.interval(sec, 99, 990);
        for (index, &enabled) in BLOCKS.iter().enumerate() {
            assert_eq!(trial.block, index + 1);
            assert_eq!(ENABLED.load(Ordering::Relaxed), enabled);
            trial.interval(sec, 90, 900);
            assert_eq!(
                (trial.measured, trial.frames, trial.draws),
                (Duration::ZERO, 0, 0)
            );
            trial.interval(sec, 5, 50);
            assert_eq!((trial.measured, trial.frames, trial.draws), (sec, 5, 50));
            trial.interval(sec, 7, 70);
        }
        trial.interval(100 * sec, 8, 80);
        assert_eq!(trial.block, 9);
        assert!(!ENABLED.load(Ordering::Relaxed));
        assert_eq!(trial.measured, Duration::ZERO);
    }
}
