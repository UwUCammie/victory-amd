use std::hint::black_box;
use std::time::Instant;

type Due = [Vec<(u64, u32, u64)>; 2];
type Order = fn(Due, usize) -> Vec<(u32, u64)>;

fn records(again: usize, fresh: usize, mut seed: u64) -> Due {
    let mut writes = (1..=(again + fresh) as u64).collect::<Vec<_>>();
    for i in (1..writes.len()).rev() {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        writes.swap(i, seed as usize % (i + 1));
    }
    let item = |&write: &u64| (write / 80, write as u32, write);
    [
        writes[..again].iter().map(item).collect(),
        writes[again..].iter().map(item).collect(),
    ]
}

fn main() {
    let mut verified = 0;
    for again in 0..=24 {
        for fresh in 0..=24 {
            for seed in [1, 3456, 68157] {
                let list = records(again, fresh, seed);
                for max in 0..=again + fresh + 2 {
                    let old = control(list.clone(), max);
                    let new = candidate(list.clone(), max);
                    assert_eq!(
                        old, new,
                        "again={again} fresh={fresh} max={max} seed={seed}"
                    );
                    verified += 1;
                }
            }
        }
    }
    eprintln!("{verified} limits and shuffled queues agree");
    println!("again,fresh,limit,repeat,control_us,candidate_us");
    for (again, fresh, max) in [
        (128, 512, 4096),
        (1000, 3097, 4096),
        (1000, 9000, 4096),
        (1000, 39000, 4096),
        (5000, 20000, 4096),
        (5000, 20000, 65536),
        (0, 10000, 4096),
        (10000, 0, 4096),
    ] {
        let lists: Vec<Due> = (1..=24)
            .map(|seed| records(again, fresh, seed * 1997))
            .collect();
        for list in &lists {
            assert_eq!(control(list.clone(), max), candidate(list.clone(), max));
        }
        let time = |select: Order| {
            let mut elapsed = 0;
            for list in &lists {
                let input = list.clone();
                let at = Instant::now();
                let out = black_box(select(black_box(input), black_box(max)));
                elapsed += at.elapsed().as_nanos();
                black_box(out);
            }
            elapsed as f64 / (1000.0 * lists.len() as f64)
        };
        for repeat in 0..9 {
            let (before, after) = if repeat % 2 == 0 {
                (time(control), time(candidate))
            } else {
                let after = time(candidate);
                (time(control), after)
            };
            println!("{again},{fresh},{max},{repeat},{before:.3},{after:.3}");
        }
    }
}
