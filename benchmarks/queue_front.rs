fn forces() -> bool { true }

mod queue {
    // MEASURED_SOURCE

    use std::sync::atomic::AtomicBool;
    static GATE: AtomicBool = AtomicBool::new(false);
    thread_local! {
        static ORDER: std::cell::RefCell<Vec<usize>> = const { std::cell::RefCell::new(Vec::new()) };
    }

    struct Task {
        index: usize,
        waits: bool,
    }

    impl Work for Task {
        type Ask = ();
        fn ask(&self) -> Option<()> { self.waits.then_some(()) }
        fn met(_: &()) -> bool { GATE.load(Relaxed) }
        fn runs(&self) -> bool { !self.waits }
        fn shows(&self) -> bool { false }
        fn go(self, forced: bool) {
            assert!(!forced);
            ORDER.with_borrow_mut(|seen| seen.push(self.index));
        }
    }

    pub(super) fn timed(blocked: bool, depth: usize) -> u128 {
        let lane = Lane::new();
        let mut elapsed = Duration::ZERO;
        let rounds: u32 = 16_000;
        let expected: Vec<_> = if blocked {
            (0..depth).filter(|n| n % 4 != 0).chain((0..depth).step_by(4)).collect()
        } else {
            (0..depth).collect()
        };
        for round in 0..=rounds {
            GATE.store(false, Relaxed);
            for index in 0..depth {
                lane.push(index % 4, [Task { index, waits: blocked && index == 0 }]);
            }
            let limit = lane.lock().next;
            let start = Instant::now();
            lane.look(limit);
            if blocked {
                GATE.store(true, Relaxed);
                lane.look(limit);
            }
            if round != 0 {
                elapsed += start.elapsed();
            }
            ORDER.with_borrow_mut(|seen| {
                assert_eq!(*seen, expected);
                seen.clear();
            });
        }
        elapsed.as_nanos() / u128::from(rounds)
    }
}

fn main() {
    for depth in [1, 16, 32] {
        for blocked in [false, true] {
            let label = if blocked { "waiting" } else { "ready" };
            println!("{label}-{depth} {}", queue::timed(blocked, depth));
        }
    }
}
