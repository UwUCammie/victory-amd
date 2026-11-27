use std::collections::BTreeMap;
use std::hint::black_box;
use std::time::Instant;

type Due = [Vec<(u64, u32, u64)>; 2];
type Scan = fn(&Queue, u64, bool) -> (Due, [u64; 5]);

struct Queue {
    slots: BTreeMap<u32, Waiting>,
}

fn control(queue: &Queue, frame: u64, due: bool) -> (Due, [u64; 5]) {
    (
        if due {
            queue.all_due(frame)
        } else {
            Due::default()
        },
        queue.census(frame),
    )
}

fn queue(amount: u32) -> Queue {
    let mut slots = BTreeMap::new();
    for index in 0..amount {
        let n = u64::from(index);
        let shuffled = n.wrapping_mul(0x9e37_79b9_7f4a_7c15);
        let due = (shuffled >> 54) % 120;
        let mapped = if shuffled >> 63 != 0 && index % 7 == 0 {
            64_000
        } else {
            0
        };
        slots.insert(
            index,
            Waiting {
                due,
                written: n % 17,
                write: n + 1,
                looks: (n % 3) as u8,
                mapped,
                checked: (0, 0, 0, 0, 0),
            },
        );
    }
    Queue { slots }
}

fn main() {
    let mut checked = 0;
    for amount in [0, 1, 2, 17, 1000, 10_000, 40_000] {
        let q = queue(amount);
        for frame in (0..145).step_by(5).chain([u64::MAX]) {
            for due in [false, true] {
                assert_eq!(control(&q, frame, due), q.snapshot(frame, due));
                checked += 1;
            }
        }
    }
    eprintln!("{checked} texture queue snapshots agree");
    println!("slots,collect,repeat,control_us,candidate_us");
    for amount in [512, 10_000, 40_000] {
        let q = queue(amount);
        for gather in [false, true] {
            let time = |scan: Scan| {
                let start = Instant::now();
                for frame in 0..80 {
                    black_box(scan(
                        black_box(&q),
                        black_box((frame * 73) % 121),
                        black_box(gather),
                    ));
                }
                start.elapsed().as_nanos() as f64 / 80_000.0
            };
            for repeat in 0..9 {
                let (old, new) = if repeat % 2 == 0 {
                    (time(control), time(Queue::snapshot))
                } else {
                    let new = time(Queue::snapshot);
                    (time(control), new)
                };
                println!("{amount},{gather},{repeat},{old:.3},{new:.3}");
            }
        }
    }
}
