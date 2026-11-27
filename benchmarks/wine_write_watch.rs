//! Measures joining two GetWriteWatch calls over a clean gap in one reservation.
use std::ffi::c_void;
use std::ptr::null_mut;
use std::time::Instant;

#[link(name = "kernel32", kind = "raw-dylib")]
unsafe extern "system" {
    fn VirtualAlloc(
        address: *mut c_void,
        size: usize,
        allocation: u32,
        protect: u32,
    ) -> *mut c_void;
    fn VirtualFree(address: *mut c_void, size: usize, free: u32) -> i32;
    fn GetWriteWatch(
        flags: u32,
        address: *mut c_void,
        size: usize,
        pages: *mut *mut c_void,
        count: *mut usize,
        granularity: *mut u32,
    ) -> u32;
}

const PAGE: usize = 4096;
const SIDE: usize = 64 << 10;
const RESERVE_COMMIT_WRITE_WATCH: u32 = 0x203000;
const READ_WRITE: u32 = 0x04;
const RELEASE: u32 = 0x8000;
const RESET: u32 = 1;

fn written(address: *mut u8, size: usize, pages: &mut [*mut c_void]) -> usize {
    let mut count = pages.len();
    let mut granularity = 0;
    // SAFETY: the allocation covers the requested range and pages holds count addresses.
    let code = unsafe {
        GetWriteWatch(
            RESET,
            address.cast(),
            size,
            pages.as_mut_ptr(),
            &mut count,
            &mut granularity,
        )
    };
    assert_eq!(code, 0, "GetWriteWatch status");
    assert_eq!(granularity as usize, PAGE);
    assert!(count <= pages.len());
    count
}

fn sample(base: *mut u8, right: usize, pages: &mut [*mut c_void], joined: bool) -> u128 {
    const REPEATS: u32 = 128;
    // SAFETY: the caller allocates the right span through right + SIDE.
    let (next, left_dirty, right_dirty) =
        unsafe { (base.add(right), base.add(PAGE), base.add(right + PAGE)) };
    let begin = Instant::now();
    for turn in 0..REPEATS {
        // SAFETY: both bytes lie within this process's live write-watched allocation.
        unsafe {
            left_dirty.write_volatile(turn as u8);
            right_dirty.write_volatile(turn as u8);
        }
        if joined {
            assert_eq!(written(base, right + SIDE, pages), 2);
            assert!(
                pages[..2].contains(&left_dirty.cast()) && pages[..2].contains(&right_dirty.cast())
            );
        } else {
            assert_eq!(written(base, SIDE, pages), 1);
            assert_eq!(pages[0], left_dirty.cast());
            assert_eq!(written(next, SIDE, pages), 1);
            assert_eq!(pages[0], right_dirty.cast());
        }
    }
    begin.elapsed().as_nanos() / u128::from(REPEATS)
}

fn main() {
    for gap_kib in [0, 64, 256, 1024, 4096, 8192] {
        let right = SIDE + (gap_kib << 10);
        let extent = right + SIDE;
        // SAFETY: explicit reserve and commit of fresh private memory.
        let base =
            unsafe { VirtualAlloc(null_mut(), extent, RESERVE_COMMIT_WRITE_WATCH, READ_WRITE) }
                .cast::<u8>();
        assert!(!base.is_null(), "allocate write-watched memory");
        for offset in (0..extent).step_by(PAGE) {
            // SAFETY: each offset lies inside the allocation.
            unsafe { base.add(offset).write_volatile(1) };
        }
        let mut pages = vec![null_mut(); extent / PAGE];
        assert_eq!(written(base, extent, &mut pages), extent / PAGE);
        assert_eq!(written(base, extent, &mut pages), 0);
        for trial in 0..9 {
            let (split, joined) = if trial % 2 == 0 {
                (
                    sample(base, right, &mut pages, false),
                    sample(base, right, &mut pages, true),
                )
            } else {
                let joined = sample(base, right, &mut pages, true);
                (sample(base, right, &mut pages, false), joined)
            };
            if trial > 0 {
                println!("{gap_kib},{split},{joined}");
            }
        }
        assert_eq!(written(base, extent, &mut pages), 0);
        // SAFETY: base is the original address, owned by this process.
        assert_ne!(unsafe { VirtualFree(base.cast(), 0, RELEASE) }, 0);
    }
}
