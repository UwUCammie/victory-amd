use std::collections::{BTreeSet, HashSet};
use std::time::Instant;

trait Slots {
    fn write(&mut self, slot: u32, buffer: bool);
    fn drain(&mut self) -> Vec<u32>;
    fn current(&self) -> Vec<u32>;
}

#[derive(Default)]
struct Before {
    live: BTreeSet<u32>,
    changed: HashSet<u32>,
}

impl Slots for Before {
    fn write(&mut self, slot: u32, buffer: bool) {
        if buffer {
            self.live.insert(slot);
        }
        if buffer || self.live.remove(&slot) {
            self.changed.insert(slot);
        }
    }
    fn drain(&mut self) -> Vec<u32> {
        std::mem::take(&mut self.changed).into_iter().collect()
    }
    fn current(&self) -> Vec<u32> {
        self.live.iter().copied().collect()
    }
}

#[derive(Default)]
struct After {
    live: SlotSet,
    changed: SlotSet,
}

impl Slots for After {
    fn write(&mut self, slot: u32, buffer: bool) {
        if buffer {
            self.live.insert(slot);
        }
        if buffer || self.live.remove(&slot) {
            self.changed.insert(slot);
        }
    }
    fn drain(&mut self) -> Vec<u32> {
        self.changed.take()
    }
    fn current(&self) -> Vec<u32> {
        self.live.slots()
    }
}

fn trial<S: Slots + Default>(writes: u32, frames: u32) -> (u128, u64) {
    let mut slots = S::default();
    for i in 0..83_000 {
        slots.write((i * 173) % 1_200_000, true);
    }
    slots.drain();
    let start = Instant::now();
    let mut checksum = 0;
    for frame in 0..frames {
        for i in 0..writes {
            let slot = ((i * 173 + frame * 157) % 90_000) * 13;
            slots.write(slot, (i + frame) % 7 != 0);
        }
        checksum += std::hint::black_box(slots.drain())
            .iter()
            .map(|&v| u64::from(v))
            .sum::<u64>();
        if frame % 16 == 0 {
            checksum += std::hint::black_box(slots.current())
                .iter()
                .map(|&v| u64::from(v))
                .sum::<u64>();
        }
    }
    (start.elapsed().as_micros(), checksum)
}

fn main() {
    for (writes, frames) in [(16u32, 48u32), (43_000, 16)] {
        for pair in 0..9 {
            let mut expected = None;
            for bits in if pair % 2 == 0 {
                [false, true]
            } else {
                [true, false]
            } {
                let (us, sum) = if bits {
                    trial::<After>(writes, frames)
                } else {
                    trial::<Before>(writes, frames)
                };
                if let Some(old) = expected {
                    assert_eq!(sum, old);
                }
                expected = Some(sum);
                if pair > 0 {
                    println!("{writes} {pair} {bits} {us}");
                }
            }
        }
    }
}
