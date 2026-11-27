use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::Cell;
use std::hint::black_box;
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
use std::sync::Arc;

type ID3D12DescriptorHeap = Arc<u32>;
type Heap = Option<ID3D12DescriptorHeap>;

#[derive(Debug, Default, PartialEq, Eq)]
struct Trace {
    bound: [Option<u32>; 2],
    kept: [Option<u32>; 2],
}

#[derive(Default)]
struct Bound(Cell<[Option<u32>; 2]>);
impl Bound {
    #[allow(non_snake_case)]
    unsafe fn SetDescriptorHeaps(&self, heaps: &[Heap]) {
        assert!(!heaps.is_empty());
        for slot in heaps {
            assert!(slot.is_some());
        }
        self.0.set(std::array::from_fn(|i| {
            heaps.get(i).and_then(Option::as_deref).copied()
        }));
    }
}

#[derive(Default)]
struct Kept(Cell<[Option<u32>; 2]>);
impl Kept {
    fn keep(&self, heap: &ID3D12DescriptorHeap) {
        let mut kept = self.0.get();
        *kept.iter_mut().find(|item| item.is_none()).unwrap() = Some(**heap);
        self.0.set(kept);
    }
}

static ALLOCS: AtomicUsize = AtomicUsize::new(0);
struct CountAlloc;

// SAFETY: requests are passed through unchanged to the system allocator.
unsafe impl GlobalAlloc for CountAlloc {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Relaxed);
        unsafe { System.alloc(layout) }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }
}

#[global_allocator]
static ALLOCATOR: CountAlloc = CountAlloc;

fn run(
    bind: fn(Heap, Heap) -> Trace,
    view: &Heap,
    sampler: &Heap,
    expected: &[Option<u32>; 2],
) -> usize {
    let before = ALLOCS.load(Relaxed);
    for _ in 0..10_000 {
        let result = black_box(bind(black_box(view.clone()), black_box(sampler.clone())));
        assert_eq!(result.bound, *expected);
        assert_eq!(result.kept, *expected);
    }
    ALLOCS.load(Relaxed) - before
}

fn main() {
    let view = Some(Arc::new(17));
    let sampler = Some(Arc::new(23));
    println!("heaps,control_allocations,candidate_allocations");
    for (name, v, s, expected) in [
        ("none", &None, &None, [None, None]),
        ("view", &view, &None, [Some(17), None]),
        ("sampler", &None, &sampler, [Some(23), None]),
        ("both", &view, &sampler, [Some(17), Some(23)]),
    ] {
        let before = run(control, v, s, &expected);
        let after = run(candidate, v, s, &expected);
        assert_eq!(before, 10_000);
        assert_eq!(after, 0);
        println!("{name},{before},{after}");
    }
}
