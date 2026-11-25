//! Integer-keyed renderer maps. Hash implementation from upstream VIctory #2102.

use std::hash::{BuildHasherDefault, Hasher};

pub(crate) type Map<K, V> = std::collections::HashMap<K, V, BuildHasherDefault<Fx>>;

/// FxHash's multiply-rotate step (finished as rustc-hash 2 does).
#[derive(Default)]
pub(crate) struct Fx(u64);

impl Hasher for Fx {
    /// Rotated, so that the bits the multiply mixed best pick the bucket:
    /// without it, aligned addresses (low bits zero) land in few buckets.
    fn finish(&self) -> u64 {
        self.0.rotate_left(26)
    }

    fn write(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.write_u64(u64::from(b));
        }
    }

    fn write_u32(&mut self, n: u32) {
        self.write_u64(u64::from(n));
    }

    fn write_u64(&mut self, n: u64) {
        self.0 = (self.0.rotate_left(5) ^ n).wrapping_mul(0x517c_c1b7_2722_0a95);
    }

    fn write_usize(&mut self, n: usize) {
        self.write_u64(n as u64);
    }
}
