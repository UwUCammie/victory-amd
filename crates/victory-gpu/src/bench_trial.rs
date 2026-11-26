//! One-launch A/B measurement of the recording-thread shadow lookup cache.
use std::sync::OnceLock;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

enum Mode {
    Fixed(bool),
    Paired,
}

fn mode() -> &'static Mode {
    static MODE: OnceLock<Mode> = OnceLock::new();
    MODE.get_or_init(
        || match std::env::var("VICTORY_SHADOW_CACHE").as_deref() {
            Ok("paired") => Mode::Paired,
            Ok("1") => Mode::Fixed(true),
            _ => Mode::Fixed(false),
        },
    )
}

static ENABLED: AtomicBool = AtomicBool::new(false);

pub(crate) fn cache_enabled() -> bool {
    match mode() {
        Mode::Fixed(value) => *value,
        Mode::Paired => ENABLED.load(Ordering::Relaxed),
    }
}

static HITS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
pub(crate) fn cache_hit() {
    if matches!(mode(), Mode::Paired) {
        // Avoid a shared atomic operation on every successful lookup.
        thread_local! { static PENDING: std::cell::Cell<u32> = const { std::cell::Cell::new(0) }; }
        PENDING.with(|pending| {
            let n = pending.get() + 1;
            if n == 256 {
                HITS.fetch_add(256, Ordering::Relaxed);
                pending.set(0);
            } else {
                pending.set(n);
            }
        });
    }
}

// Each four-block set balances a linear drift. A longer trial reverses the order.
const BLOCKS: [bool; 8] = [false, true, true, false, true, false, false, true];

pub(crate) struct Trial {
    block: usize, // 0 is warm-up, 1 through 8 are measured
    duration: Duration,
    block_duration: Duration,
    elapsed: Duration,
    measured: Duration,
    frames: u64,
    draws: u64,
    hits_before: u64,
}

impl Trial {
    pub(crate) fn from_env() -> Option<Self> {
        if !matches!(mode(), Mode::Paired) {
            return None;
        }
        fn seconds(key: &str, default: u64, min: u64) -> Duration {
            let value = std::env::var(key)
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(default);
            Duration::from_secs(value.max(min))
        }
        let duration = seconds("VICTORY_BENCH_WARMUP_SECONDS", 150, 0);
        let block_duration = seconds("VICTORY_BENCH_BLOCK_SECONDS", 40, 5);
        Some(Self::new(duration, block_duration))
    }

    fn new(duration: Duration, block_duration: Duration) -> Self {
        ENABLED.store(false, Ordering::Relaxed);
        Self {
            block: 0,
            duration,
            block_duration,
            elapsed: Duration::ZERO,
            measured: Duration::ZERO,
            frames: 0,
            draws: 0,
            hits_before: 0,
        }
    }

    pub(crate) fn interval(&mut self, dt: Duration, frames: u32, draws: u64) {
        if self.block > BLOCKS.len() {
            return;
        }
        let hits = HITS.load(Ordering::Relaxed);
        if self.block > 0 {
            if self.elapsed.is_zero() {
                // Discard the first complete reporting interval after each boundary.
                self.hits_before = hits;
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
            tracing::info!(target: "victory_bench", kind = "shadow_cache", block = self.block,
                enabled = BLOCKS[self.block - 1], frames = self.frames,
                interval_us = self.measured.as_micros() as u64, draws = self.draws,
                work_units = hits - self.hits_before, block_s = self.block_duration.as_secs(),
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
        let mut trial = Trial::new(2 * sec, 3 * sec);
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
