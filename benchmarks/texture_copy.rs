//! Linux CPU microbenchmark. Place the two versions of texture.rs beside
//! this file as reference.rs and candidate.rs. Compile with rustc -O.
//! Output columns: case, direction, pair, version, copies, thread CPU ns.
#![allow(dead_code)]
mod candidate;
mod reference;

use std::hint::black_box;
use std::os::raw::{c_int, c_long};

#[repr(C)]
struct Timespec {
    seconds: c_long,
    nanos: c_long,
}

unsafe extern "C" {
    fn clock_gettime(clock: c_int, result: *mut Timespec) -> c_int;
}

fn thread_cpu_ns() -> u64 {
    let mut time = Timespec {
        seconds: 0,
        nanos: 0,
    };
    // SAFETY: a writable Linux timespec, using CLOCK_THREAD_CPUTIME_ID.
    assert_eq!(unsafe { clock_gettime(3, &mut time) }, 0);
    time.seconds as u64 * 1_000_000_000 + time.nanos as u64
}

struct Case {
    name: &'static str,
    width: u32,
    height: u32,
    element_bytes: u32,
    block: u32,
    swizzle: u32,
    copies: usize,
}

macro_rules! layout {
    ($version:ident, $case:ident) => {
        $version::Layout::new(&$version::Desc {
            dimension: $version::Dimension::Tex2d,
            width: $case.width,
            height: $case.height,
            depth: 1,
            mips: 5,
            element_bytes: $case.element_bytes,
            block: $case.block,
            samples: 1,
            swizzle: $version::Swizzle($case.swizzle),
        })
        .unwrap()
    };
}

fn run(case: Case) {
    let reference = layout!(reference, case);
    let candidate = layout!(candidate, case);
    assert_eq!(reference.size, candidate.size);
    for (index, mip) in reference.mips.iter().enumerate() {
        let level = index as u32;
        let row_bytes = mip.width as usize * case.element_bytes as usize;
        let stride = row_bytes.next_multiple_of(256);
        let plane = stride * mip.height as usize;
        let linear: Vec<_> = (0..plane)
            .map(|i| ((i ^ (i >> 9) ^ (i >> 15)) % 251) as u8)
            .collect();
        let mut tiled = vec![0xab; reference.size as usize];
        let mut actual_tiled = tiled.clone();
        let mut output = vec![0xcd; plane];
        let mut actual_output = output.clone();
        reference
            .tile(&mut tiled, level, 0, &linear, stride, plane)
            .unwrap();
        candidate
            .tile(&mut actual_tiled, level, 0, &linear, stride, plane)
            .unwrap();
        assert_eq!(tiled, actual_tiled);
        reference
            .detile(&tiled, level, 0, &mut output, stride, plane)
            .unwrap();
        candidate
            .detile(&actual_tiled, level, 0, &mut actual_output, stride, plane)
            .unwrap();
        assert_eq!(output, actual_output);
        for (row, input) in output.chunks_exact(stride).zip(linear.chunks_exact(stride)) {
            assert_eq!(row[..row_bytes], input[..row_bytes]);
            assert!(row[row_bytes..].iter().all(|&byte| byte == 0xcd));
        }
        if level != 0 {
            continue;
        }
        for detile in [true, false] {
            let direction = if detile { "detile" } else { "tile" };
            // Both paths read and write the same allocations while timed.
            macro_rules! copy {
                ($layout:ident) => {
                    for _ in 0..case.copies {
                        if detile {
                            $layout
                                .detile(
                                    black_box(&tiled),
                                    level,
                                    0,
                                    black_box(&mut output),
                                    stride,
                                    plane,
                                )
                                .unwrap();
                        } else {
                            $layout
                                .tile(
                                    black_box(&mut tiled),
                                    level,
                                    0,
                                    black_box(&linear),
                                    stride,
                                    plane,
                                )
                                .unwrap();
                        }
                    }
                };
            }
            for pair in 0..15 {
                for old in [pair % 2 == 0, pair % 2 != 0] {
                    let start = thread_cpu_ns();
                    if old {
                        copy!(reference);
                    } else {
                        copy!(candidate);
                    }
                    let ns = thread_cpu_ns() - start;
                    let version = if old { "old" } else { "new" };
                    println!(
                        "{} {direction} {pair} {version} {} {ns}",
                        case.name, case.copies
                    );
                }
            }
        }
    }
}

fn main() {
    for (name, width, height, element_bytes, block, swizzle, copies) in [
        ("rgba720", 1280, 720, 4, 1, 9, 12),
        ("bc720", 1280, 720, 16, 4, 9, 12),
        ("odd", 1279, 719, 1, 1, 5, 12),
        ("small", 32, 32, 4, 1, 9, 8192),
    ] {
        run(Case {
            name,
            width,
            height,
            element_bytes,
            block,
            swizzle,
            copies,
        });
    }
}
