use shadow::Shadow;
use std::cell::Cell;
use std::hint::black_box;
use std::sync::Arc;
use std::time::Instant;

thread_local! {
    static VIEW_BYTES: Cell<bool> = const { Cell::new(true) };
    static RAW_TWINS: Cell<u32> = const { Cell::new(1) };
}

fn view_bytes() -> bool {
    VIEW_BYTES.get()
}

fn probe_view_limit() {}

mod resource {
    pub fn element(format: u32) -> Option<(u64, u64)> {
        (format == 42).then_some((4, 1))
    }
}

extern crate self as victory_shader;
mod emit {
    pub fn raw_views() -> u32 {
        super::RAW_TWINS.get()
    }
}

mod shadow {
    use std::cell::RefCell;
    use std::sync::Arc;

    pub struct Shadow {
        pub start: u64,
        pub len: u64,
        pub padding: u64,
    }

    impl Shadow {
        pub fn offset_in(&self, address: u64) -> Option<u64> {
            address.checked_sub(self.start).filter(|&at| at < self.len)
        }

        pub fn offset(&self, address: u64) -> u64 {
            address - self.start + self.padding
        }
    }

    thread_local! {
        pub static EXACT: RefCell<Option<Arc<Shadow>>> = const { RefCell::new(None) };
    }

    #[inline(never)]
    pub fn exact(_start: u64, _len: u64) -> Option<Arc<Shadow>> {
        EXACT.with(|slot| slot.borrow().clone())
    }
}

type Kind = (u32, bool, u32);

#[inline(never)]
fn control_differs(shadow: &Arc<Shadow>, start: u64, len: u64, kind: Kind) -> bool {
    let home = view_home(Arc::clone(shadow), start, len, kind);
    !Arc::ptr_eq(&home, shadow)
}

#[inline(never)]
fn candidate_differs(shadow: &Arc<Shadow>, start: u64, len: u64, kind: Kind) -> bool {
    separate_view_copy(shadow, start, len, kind).is_some()
}

fn main() {
    let backing = Arc::new(Shadow {
        start: 0x1000,
        len: 4096,
        padding: 0,
    });
    let own = Arc::new(Shadow {
        start: 0x1008,
        len: 128,
        padding: 0,
    });
    let placed = Arc::new(Shadow {
        start: 0x1000,
        len: 4096,
        padding: 8,
    });
    let raw = (0, true, 0);
    let typed = (0, false, 42);
    let structured = (24, false, 0);
    let mut checked = 0;
    for base in [&backing, &placed] {
        for enabled in [false, true] {
            VIEW_BYTES.set(enabled);
            for twins in [0, 1] {
                RAW_TWINS.set(twins);
                for exact in [None, Some(base), Some(&own)] {
                    shadow::EXACT.with(|slot| slot.replace(exact.cloned()));
                    for kind in [raw, typed, structured] {
                        for address in [
                            0, 0xfff, 0x1000, 0x1001, 0x1008, 0x1010, 0x1018, 0x1fff, 0x2000,
                        ] {
                            let old = view_home(Arc::clone(base), address, 128, kind);
                            let new = separate_view_copy(base, address, 128, kind);
                            assert_eq!(new.is_some(), !Arc::ptr_eq(&old, base));
                            assert!(Arc::ptr_eq(&old, new.as_ref().unwrap_or(base)));
                            checked += 1;
                        }
                    }
                }
            }
        }
    }
    eprintln!("{checked} copy-selection cases agree");
    VIEW_BYTES.set(true);
    RAW_TWINS.set(1);
    shadow::EXACT.with(|slot| slot.replace(Some(Arc::clone(&own))));
    println!("case,repeat,control_ns,candidate_ns");
    for (name, kind, first) in [
        ("raw-aligned", raw, 0),
        ("typed-aligned", typed, 0),
        ("raw-separate", raw, 8),
        ("raw-outside", raw, 4096),
    ] {
        let time = |decide: fn(&Arc<Shadow>, u64, u64, Kind) -> bool| {
            let start = Instant::now();
            for iteration in 0..120_000 {
                let address = backing.start + first + (iteration % 64) * 16;
                black_box(decide(
                    black_box(&backing),
                    black_box(address),
                    black_box(128),
                    black_box(kind),
                ));
            }
            start.elapsed().as_nanos() as f64 / 120_000.0
        };
        for repeat in 0..15 {
            let (before, after) = if repeat % 2 == 0 {
                (time(control_differs), time(candidate_differs))
            } else {
                let after = time(candidate_differs);
                (time(control_differs), after)
            };
            println!("{name},{repeat},{before:.3},{after:.3}");
        }
    }
}
