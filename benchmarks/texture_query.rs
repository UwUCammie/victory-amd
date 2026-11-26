use std::collections::BTreeMap;
use std::hint::black_box;
use std::ops::Range;
use std::time::Instant;

// The query functions below come from the revision under test. The fixture
// supplies a populated journal, so it measures how an existing answer is read.
struct Journal { written: BTreeMap<usize, u64> }
static JOURNAL: std::sync::OnceLock<Journal> = std::sync::OnceLock::new();
fn with_writes<T>(start: usize, end: usize, _: bool, read: impl Fn(&Journal, Range<usize>) -> T) -> Option<(u64, T)> {
    Some((12, read(JOURNAL.get().unwrap(), start..end)))
}

// MEASURED_SOURCE

fn query(vector: bool, start: usize, end: usize, since: u64) -> bool {
    if vector {
        let (_, pages) = writes(start, end, false).unwrap();
        since != 0 && pages.iter().all(|&(_, write)| write <= since)
    } else {
        unchanged_since(start, end, false, since).unwrap().1
    }
}

fn main() {
    let vector = match std::env::args().nth(1).as_deref() {
        Some("list") => true,
        Some("summary") => false,
        _ => panic!("expected list or summary"),
    };
    let written = (0..8192).filter(|page| page % 7 != 0)
        .map(|page| (page, if page % 64 == 3 { 11 } else { 10 })).collect();
    JOURNAL.set(Journal { written }).ok().unwrap();
    for pages in [1, 16, 256, 1024] {
        let starts: Vec<usize> = (0..193).map(|i| i * 31 % 6100).collect();
        for (case, since) in [("first", 0), ("some-written", 10), ("all-clean", 11)] {
            for &start in &starts {
                let expected = since != 0 && (start..start + pages)
                    .filter(|page| page % 7 != 0)
                    .all(|page| (if page % 64 == 3 { 11 } else { 10 }) <= since);
                assert_eq!(query(vector, start, start + pages, since), expected);
            }
            let repeats = 1 + 4096 / pages;
            let timer = Instant::now();
            for _ in 0..repeats {
                for &start in &starts {
                    black_box(query(black_box(vector), black_box(start), black_box(start + pages), black_box(since)));
                }
            }
            println!("{pages}/{case} {}", timer.elapsed().as_nanos() / (starts.len() * repeats) as u128);
        }
    }
}
