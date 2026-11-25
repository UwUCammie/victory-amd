# First-room measurements on the RX 7900 XT

This branch carries the accepted-present counter from [PR #1154](https://github.com/fxceless/victory-fork/pull/1154) and a release-build sampling feature. To run it on your own local installation, build from the workspace root.

```sh
cargo build --locked --release -p victory -p victory-gpu --features victory-gpu/frame-sampling
```

Play the same route and keep each run’s output locally. The frame line reports successful presents, elapsed microseconds and executed draw calls. Set `VICTORY_BENCH_READS=1` to sample one in 67 host reads and one in 257 graphics viewport binds per thread. The report contains the busiest source call sites and viewport sizes over ten seconds. The sampling adds work. Use identical settings on both sides of a comparison.

```sh
python3 benchmarks/first_room.py path/to/run.log --start 150 --stop 225
```

The time origin is the first timestamp in the log. Only complete present intervals inside the window count. Divide the total presents by total elapsed time. Confirm the room visually and check the full session for device loss before comparing runs.

## Measurements

Ryzen 7 9700X, RX 7900 XT, RADV 26.3.1, Wine 11.22, vkd3d-proton v3.1-83. I used the Series X profile, the first room, a warmed cache and a separate offline test prefix. Each session lasted 230 seconds. The table includes changes under test in an integration build. A successful present confirms that the swapchain accepted a frame. Draw count and occasional private stills are separate checks on the workload.

| Variant | Presents | Seconds | FPS | Draws/frame |
| --- | ---: | ---: | ---: | ---: |
| 64 KiB readbacks | 663 | 73.99 | 8.96 | 4,895 |
| 64 KiB readbacks, same binary and settings, repeat | 610 | 74.02 | 8.24 | 4,870 |
| 16 KiB readbacks | 752 | 74.31 | 10.12 | 4,829 |
| 16 KiB readbacks, same binary and settings, repeat | 538 | 73.74 | 7.30 | 4,867 |
| 4 KiB readbacks | 591 | 73.67 | 8.02 | 4,875 |
| 16 KiB, levels on demand | 624 | 73.76 | 8.46 | 4,905 |
| 16 KiB, Vulkan descriptor buffers | 693 | 74.07 | 9.36 | 4,873 |
| 16 KiB, host-read and viewport sampling | 655 | 73.82 | 8.87 | 4,854 |
| Same sampling build, 1080p display setting | 555 | 73.22 | 7.58 | 4,870 |
| 16 KiB, consecutive GPU fetch commands joined, sampling on | 384 | 73.12 | 5.25 | 4,931 |
| 16 KiB, reusable merge scratch | 588 | 73.89 | 7.96 | 4,881 |
| Same scratch build with shared copy-worker completion | 693 | 74.37 | 9.32 | 4,919 |

For the piece-size trial, the renderer used asynchronous submit, two queues, parallel refresh and merge, the 64-lane card compare, and a zero merge gap. The only setting changed between those three rows was `VICTORY_CARD_PIECE_KB`. The measurement branch supplies the sampler and analysis tools. The figures came from an integration build with additional changes, including [registration lookup](https://github.com/fxceless/victory-fork/pull/1142), [parallel refresh timing](https://github.com/fxceless/victory-fork/pull/1135), [descriptor bookkeeping](https://github.com/fxceless/victory-fork/pull/1128), and [relay page ordering](https://github.com/fxceless/victory-fork/pull/1066).

The readback-size rows all use the same executable. Median copy-queue readback fell from 93.5 to 85.8 to 59.7 MB/frame as pieces got smaller. The 4 KiB copy queue took 6.3 ms/frame, versus 4.7 ms at 16 KiB. The two 16 KiB baseline runs averaged 8.71 FPS together (1,290 presents in 148.05 seconds), and the two at 64 KiB averaged 8.60 (1,273 presents in 148.01 seconds). The desktop shared the GPU, and some runs overlapped low-priority builds. [Readback PR](https://github.com/fxceless/victory-fork/pull/1164)

The two display settings both produced a 3840×2160 swapchain. The most frequently sampled viewport was 2560×1440 in both, followed by 2048×2048. The first room was visible in a capture from each run. [Display measurements](https://github.com/fxceless/victory-fork/issues/10#issuecomment-7176659252)

On-demand levels avoided 3,057 MB of logical mip backing at the final sample. The tile pool held 896 MB of heaps. Joining adjacent GPU readback commands removed about 4,152 copy commands/frame. CPU preparation and GPU waits both increased in that trial. [Mip backing](https://github.com/fxceless/victory-fork/issues/898#issuecomment-7176439226) · [Readback commands](https://github.com/fxceless/victory-fork/pull/824#issuecomment-7176776652)

## Copy-worker benchmark

From a checkout with both refs available, run the native benchmark with Python 3 and Rust. It uses the pool implementation from each revision, checks that every submitted job completed and alternates run order. The buffer-update workload uses synthetic bytes.

```sh
git fetch https://github.com/fxceless/victory-fork.git refs/pull/1172/head
python3 benchmarks/copy_pool.py 9c184b35 FETCH_HEAD
```

Eight paired trials on the 9700X gave median times of 21.40 and 11.15 ms for two callers each submitting 64 batches of 512 counter jobs. Two callers updating 1–5 KiB buffers took 7.77 and 5.13 ms. [Worker-pool PR](https://github.com/fxceless/victory-fork/pull/1172)

The [renderer trial sources](https://github.com/UwUCammie/victory-amd/tree/bench/radv-renderer-trials) include the optional registered-range cache, the adjacent GPU readback command trial and a CPU benchmark of descriptor bookkeeping. The [sparse indirect draw test](https://github.com/UwUCammie/victory-amd/commit/2ba2d770080da9ff507701a09b1103553ccfbfbb) runs on the head of [PR #1171](https://github.com/fxceless/victory-fork/pull/1171). The consecutive and sparse cases both passed on the physical RX 7900 XT.

The combined gather, copy-worker and registration-cache build averaged 674 accepted presents in 73.42 s (9.18 FPS, 4,858 draws/frame). The first room and character were visible at 175 s. A separate [descriptor-table integration](https://github.com/UwUCammie/victory-amd/tree/test/1192-half-views) initially ran at 30 FPS on the account picker with about 14 draws/frame. Its release build omitted the scripted-input feature. That run is excluded from the gameplay comparison.

## Descriptor slot bookkeeping

The native Rust benchmark compares the original B-tree and hash set with the bitset implementation from a Git revision. It starts with 83,000 live buffer descriptors in a 1.2-million-slot heap, checks a checksum of both sets, and alternates order over eight timed pairs. Each line gives the writes per frame, pair number, whether the bitset was used, and elapsed microseconds.

```sh
git fetch https://github.com/UwUCammie/victory-amd.git perf/ordered-buffer-slot-bits
python3 benchmarks/slot_sets.py FETCH_HEAD
```

On the 9700X, 16 frames of 43,000 synthetic writes each took 73.56 ms with the original sets and 2.53 ms with the bitsets (medians). At 16 writes per frame over 48 frames the medians were 0.38 and 0.51 ms. The gameplay trial used an earlier integration build and averaged 9.04 FPS, within the range of the control runs.

## Gathering indirect draws

The integration build included [the indirect gather change](https://github.com/fxceless/victory-fork/pull/1171). The first pair used one executable with gathering enabled then disabled. A second executable added cumulative pass and record counts and ran in reverse order.

| Pair | Gathering | Accepted presents | Seconds | FPS | Draws/frame |
| --- | --- | ---: | ---: | ---: | ---: |
| First | On | 675 | 73.81 | 9.15 | 4,830 |
| First | Off | 448 | 74.21 | 6.04 | 4,874 |
| Reverse | Off | 636 | 73.94 | 8.60 | 4,836 |
| Reverse | On | 577 | 73.33 | 7.87 | 4,977 |

In the reverse pair, the enabled build counted 24,231 gather passes and 1,974,917 records between the samples bounding the measured intervals. Both counters stayed at zero with gathering disabled. Pooling both pairs gives 8.51 FPS on and 7.32 off. The faster setting varied between pairs on this shared desktop.
