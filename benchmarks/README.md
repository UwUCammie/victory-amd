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

## November renderer trials

With the November 26 renderer build, plain fills, indexed submission steps and fill waits enabled, the RX 7900 XT recorded 456 accepted presents in 73.86 s (6.17 FPS, 4,936 draws/frame). The character and courtyard were visible at 175 s. This build used the serial descriptor scan. [Build source](https://github.com/UwUCammie/victory-amd/tree/bench/fx-refresh-nov26)

On the Series S profile with the interface compositor enabled, the unmodified upscaler showed the movement prompt over a black world. Its 532 accepted presents are excluded from gameplay FPS. Adding a packed RGB9E5 destination restored the character and courtyard in private checks at 175 and 217 s. Some scenery still shimmered. All 13 sampled dispatches wrote the stretched image. The first patched run omitted the interval sampler. A separate patched build with scripted input and sampling enabled then recorded 492 accepted presents in 73.73 s (6.67 FPS, 4,487 draws/frame). The 175 s check again showed the room. [Series S fix and GPU pixel test](https://github.com/Tissma95/victory-fork/pull/1)

The descriptor-table trial with scripted input enabled ended with a device removal during startup and produced no first-room sample. [Trial report](https://github.com/fxceless/victory-fork/pull/1192#issuecomment-7178160485)


With captured descriptor headers applied on top of the parallel-scan PR, the same executable ran the serial and parallel paths in the order shown. Both reached the character and courtyard. The small difference is within the variation seen across earlier runs on this shared desktop. [Build](https://github.com/UwUCammie/victory-amd/tree/bench/fx-parallel-snapshots-radv) · [Upstream results](https://github.com/fxceless/victory-fork/pull/1202#issuecomment-7178790298)

| Descriptor scan | Accepted presents | Seconds | FPS | Draws/frame | Median reported descriptor sync (ms/frame) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Serial | 450 | 73.64 | 6.11 | 4,919 | 42.67 |
| Parallel | 461 | 73.97 | 6.23 | 4,873 | 40.03 |

## Command-list recording

On the gather and worker integration, one executable ran the same first-room route with target-bind and unaligned root-CBV reuse enabled, then disabled. Pipeline-object retention stayed enabled. Both runs showed the character and courtyard at 175 s. Room lighting differed between captures, and one pair does not isolate the cause.

| Reuse target binds and root CBVs | Accepted presents | Seconds | FPS | Avoided target binds | Root-CBV cache hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| On | 699 | 73.92 | 9.46 | 7,689 | 0 |
| Off | 731 | 73.57 | 9.94 | 0 | 0 |

The sampler also counted 950,166 and 992,228 repeated pipeline-retain requests respectively. These are cumulative-counter differences over the measured intervals. The same GPU passed the target rewrite/replay, deferred CBV write and pipeline lifetime tests. [Build and counters](https://github.com/UwUCammie/victory-amd/tree/bench/radv-recording-reuse) · [Upstream results](https://github.com/fxceless/victory-fork/pull/1215#issuecomment-7178947611)

## Gathering indirect arguments at copy time

One 390-second run alternated the placement of the indirect-argument gather every 20 seconds. The character and courtyard were visible at 175 and 315 seconds. Between 150 and 385 seconds we counted complete present intervals inside each phase, excluding the first second after each switch.

| Gather at copy time | Accepted presents | Seconds | FPS | Draws/frame |
| --- | ---: | ---: | ---: | ---: |
| Off | 701 | 106.06 | 6.61 | 4,781 |
| On | 698 | 104.62 | 6.67 | 4,799 |

The 0.06 FPS difference gives little reason to prefer either mode in this room. Recalculate with `python3 benchmarks/gather_by_copy.py run.log`. [Build and counters](https://github.com/UwUCammie/victory-amd/tree/bench/radv-indirect-by-copy) · [Upstream change](https://github.com/fxceless/victory-fork/commit/006c353)

## In-place title memory on RADV

The same executable and input route ran with in-place import off, then at level 4 with the pool enabled. The control reached the character and courtyard and recorded 356 accepted presents in 73.82 s (4.82 FPS, 5,032 draws/frame). The level-4 run was still on a white transition screen at the late visual check. It accepted six presents in 52.42 s of complete intervals inside the measurement window and is excluded from gameplay FPS.

Level 4 exercised the import path. At the final report, the arenas held 9.99 GiB locked across two private parts and seven sections. The runtime reported 10,093 windows placed (1,728 MB cumulative) and zero title buffers placed. Both runs reached the 230-second timeout. The bounded synthetic GPU test separately passed reads and writes at a nonzero offset. [Build](https://github.com/UwUCammie/victory-amd/tree/bench/radv-inplace-first-room) · [Physical import test](https://github.com/sirrus98/victory-fork/pull/1)

## Time to compare the cold-descriptor scan

The fixed-setting reference ran the same binary in two 230-second sessions. It reached the first room in both by the 120-second private visual check. The 150–225 s windows gave 447 presents in 74.17 s (6.03 FPS) off and 421 in 74.08 s (5.68 FPS) on. The skipped-slot counter rose by 1,644,920 with the scan on and stayed at zero with it off.

The one-launch trial used the same route, a 120-second warm-up, and 20-second blocks with the first reporting interval excluded from each. The room was visible at 120 and 246 seconds. Time to result is measured from the first logged timestamp to the last required block, or to the closing report of the second separate-process window. Both fixed runs together occupied 461.3 seconds between their first and last logged activity.

| Method | Seconds to result | Measured seconds off / on | FPS off / on |
| --- | ---: | ---: | ---: |
| Two launches | 457.8 | 74.17 / 74.08 | 6.03 / 5.68 |
| One launch, first four blocks | 203.5 | 39.20 / 39.29 | 5.79 / 5.50 |
| Same launch, all eight blocks | 286.0 | 78.20 / 78.35 | 5.95 / 5.73 |

The eight-block run saved 172 seconds (38%) and gave each setting four more measured seconds than the two-launch reference. On-minus-off differences for its four pairs were −0.39, −0.19, −0.16 and −0.12 FPS. The scan skipped 1,747,928 slots while enabled and zero while disabled. Synthetic sparse heaps benefited from the scan, but these gameplay trials favor leaving it off on this setup. [One-launch build and reporter](https://github.com/UwUCammie/victory-amd/tree/545ebe2/benchmarks) · [Portable regression](https://github.com/nicolasveilleux/victory-fork/pull/2) · [Separate-launch build](https://github.com/UwUCammie/victory-amd/tree/09e87b0)

## Card upload batching

A second use of the one-launch method tested the upload and hash ordering from PR #1227. This build used the 64 KiB card-buffer threshold, a 120-second warm-up and eight 20-second blocks. First-room checks at 120 and 246 seconds showed the character and courtyard. The four-pair result was available at 286.2 seconds.

| Batch uploads and hashes | Accepted presents | Seconds | FPS | Draws/frame | Buffers in groups of two or more |
| --- | ---: | ---: | ---: | ---: | ---: |
| Off | 335 | 77.46 | 4.33 | 4,834 | 0 |
| On | 423 | 78.77 | 5.37 | 4,866 | 190,194 |

Each adjacent pair favored batching by 0.99–1.10 FPS. The two-buffer GPU fixture checks four read-back dwords and four before-hashes over two submissions. It passed in both fixed modes. [Build and reporter](https://github.com/UwUCammie/victory-amd/tree/0454795/benchmarks) · [Fixture](https://github.com/KyleS98/victory-fork/pull/4)

## Shorter first-room warm-up

With the existing release benchmark binary, ordinary Enter taps left the opening cutscene on screen at 60, 80 and 100 seconds. The first-room character and courtyard were visible at 150 and 200 seconds. The standard 150–225 s measurement recorded 584 accepted presents in 74.06 s (7.89 FPS).

In a second run with the same settings, holding the normal skip button for 4.4 seconds starting at input time 50 s put the title in transition at 60 s and in the first room by 80 s. The room remained visible at 100 and 150 s. The complete 90–165 s intervals gave 645 accepted presents in 74.05 s (8.71 FPS). The original executable produced the hold using overlapping 0.2 s Enter taps. These two FPS observations describe different visits to the room.

The gather and worker build then used the same early route to test card batching at its usual 1 MiB card-buffer threshold and with 16 KiB readbacks. Its four-block screen finished at 173.3 s and all eight blocks at 254.6 s. The photos at 80 and 210 s confirmed the room. The full result was 665 accepted presents in 77.17 s (8.62 FPS) off and 699 in 78.17 s (8.94 FPS) on. Pair differences were +1.13, +0.01, −0.02 and +0.19 FPS. The counter recorded 43,778 buffers batched. Most of the difference came from the first pair. [Build](https://github.com/UwUCammie/victory-amd/tree/243edc9) · [Normal cutscene skip in the Steenax6 fork](https://github.com/Steenax6/VIctory-NVID/blob/steenax/README.md)

A separate build on fxceless main `c9092ec` used one timed input entry, `50:Enter:4.4`. Its prologue transition was visible at 65 s and the character and courtyard at 80, 110 and 220 s. This run also tested the new heap cutoff without a second launch. The setting alternated every 20 s. From 90–250 s, qualifying intervals gave 407 accepted presents in 70.99 s (5.73 FPS, 4,833 draws/frame) off and 420 in 70.97 s (5.92 FPS, 4,834 draws/frame) on. Median reported descriptor-sync time was 19.87 and 19.77 ms/frame, respectively. The difference is small in this one scene. Recalculate with `python3 benchmarks/gather_by_copy.py run.log --switch VICTORY_HEAP_SYNC_CUT --start 90 --stop 250`. [Timed input PR](https://github.com/fxceless/victory-fork/pull/1236) · [Build](https://github.com/UwUCammie/victory-amd/tree/beddd22)

## AVX2 changed-run scan

The same RX 7900 XT release build compared SSE2 and AVX2 over eight 20-second blocks. The character and courtyard were visible at 80 and 210 seconds. All eight blocks finished at 256.2 seconds. The SSE2 blocks produced 700 accepted presents in 77.39 s (9.05 FPS, 4,858 draws/frame). The AVX2 blocks produced 720 in 79.13 s (9.10 FPS, 4,805 draws/frame). The counter recorded 929 MiB going through the AVX2 scan with it enabled and zero with it disabled. On-minus-off differences for the four adjacent pairs were +0.07, +0.00, +0.08 and +0.06 FPS. The CPU fixture showed a larger improvement for sparse changes, but it barely moved frame rate in this room. [Benchmark build and reporter](https://github.com/UwUCammie/victory-amd/tree/d372cae/benchmarks) · [Upstream change](https://github.com/fxceless/victory-fork/pull/1233)

Immediately after block eight, a five-second Linux user-mode CPU profile sampled the same process with the trial back on SSE2. Of 11,136 samples, 4,779 landed in the open-source runtime image. Its most sampled routines were `victory_copy_guarded_at` (674), `shadow::merge_piece` (329), `draw::State::bind` (225), and `shadow::lookup` (159). On the submit thread, `victory_copy_guarded_at` accounted for 191 of 778 runtime-image samples. These counts omit time spent waiting and come from a single short window. The profile used the time between the final measurement and the normal process timeout.

## Profiling after the comparison

On Linux with Wine, start the helper while the eight-block comparison is running. Give it the process ID of the Wine process with the matching renderer executable mapped. Keep that executable and its matching PDB in the same directory. Allow at least the requested profile duration plus a few seconds before the runner ends the process.

```sh
python3 benchmarks/profile_after_trial.py run.log /path/to/victory.exe "$pid" shadow_cache --seconds 5
```

The helper waits for block eight, samples user-mode CPU time with Linux perf, then uses llvm-symbolizer to count samples that landed in the open-source runtime. The timed comparison ends before profiling starts. The raw recording lives in a temporary directory. Waiting on the GPU does not produce CPU samples.

I also tried the registration-only shadow cache from #1224, with its fill and retirement changes disabled. The first room was visible at 80 and 210 s. Eight blocks took 255.0 s. The cache recorded 106,684,416 hits during the enabled intervals. The two settings produced 515 presents in 77.99 s (6.60 FPS) off and 508 in 76.86 s (6.61 FPS) on. Pair differences were +0.48, −0.08, −0.43 and +0.06 FPS. A low-priority two-job build overlapped the final eight seconds of the last block. The first three pairs also split directions. The helper then collected 3,353 runtime-image samples in five seconds using the same launch. [Benchmark build](https://github.com/UwUCammie/victory-amd/tree/f57d218) · [Upstream changes](https://github.com/fxceless/victory-fork/pull/1224)

The full cache from #1237 also remembers loose windows. On its branch plus the two lifetime fixes, the room was visible at 80 and 210 seconds. Eight blocks finished at 256.8 s. Off gave 473 presents in 78.59 s (6.02 FPS, 4,784 draws/frame). On gave 474 in 78.93 s (6.01 FPS, 4,813 draws/frame), with 131,969,280 measured cache hits. Pair differences were +0.14, +0.05, −0.04 and −0.20 FPS. Both modes ran the fixes. This comparison measures enabling the cache on the patched build. [Build](https://github.com/UwUCammie/victory-amd/tree/ed9ff4e) · [Lifetime fixes and synthetic regressions](https://github.com/KyleS98/victory-fork/pull/5)

## Running focused Windows tests together

The Rust test executable accepts several exact test names in one launch. For the two independent shadow-cache regressions in [PR #1245](https://github.com/fxceless/victory-fork/pull/1245), I used the same Windows test binary, Wine prefix and physical RX 7900 XT for each measurement. Running them separately took 10.098, 9.711 and 9.692 s per pair. Running both serially in one process took 4.920, 4.938 and 4.902 s. The median dropped from 9.711 to 4.920 s, a 49% reduction. These times include Wine startup and exclude compilation. Both exact names passed in every group, with no skips.

```sh
wine "$gpu_test_exe" --exact \
  shadow::registration_tests::a_pending_registration_invalidates_readers_of_the_old_table \
  shadow::window_cache_tests::cached_window_removed_by_sweep_is_replaced \
  --test-threads=1 --nocapture
```

Build the binary once with `cargo test -p victory-gpu --lib --target x86_64-pc-windows-msvc --no-run`. The grouped command is for cases sharing the same process configuration. Trials that compare switches read once at process startup still need separate launches.

## Testing the relay merge without the game

The independent Linux fixture imports the renderer's AVX2 merge code. It compares always storing the 32-byte vector with the equality check from #1178, which avoids loading or modifying the destination if the GPU and reference bytes match. Each pattern uses 4 MiB of synthetic data. Both paths have to match the expected reference bytes, destination bytes and change flag. The renderer's three alignment, tail and CPU-write tests also pass in 0.02 s.

Five complete fixture runs on a Ryzen 7 9700X after the game exited took a median of 0.048 s with the binary already built. Median kernel times in microseconds were 131 → 92 for equal inputs, 133 → 72 for one changed byte per 4 KiB and 134 → 147 for changes in every other byte. The left figure is the existing vector merge, the right skips equal vectors. [CPU fixture and source](https://github.com/UwUCammie/victory-amd/tree/8406243/benchmarks) · [Upstream merge implementation](https://github.com/fxceless/victory-fork/pull/1178)

In the first eight-block room test, accepted presents averaged 9.14/s off and 9.43/s on (702/76.83 s and 738/78.25 s). The enabled path examined 39,027 MiB. But private captures at 80 and 210 s were pixel-identical, and another near the end was identical too. The picture changed at 260 s after all the measured blocks. These figures are present rates only. I excluded this run from the gameplay comparison.

## Checking visible frame changes in the same launch

A four-block repeat sampled the center of the Wine game window for five seconds inside each block. The helper reads a 256×144 crop with the cursor hidden and counts adjacent samples whose luma changes. It saves no images. A synthetic static source produced zero changes in 60 samples. A 10 Hz animation sampled at 30 Hz produced 19, and a 30 Hz animation produced 59. A stationary scene can have fewer changes than presents. Shimmer can also change pixels, so we still check that the character and room are visible.

| Start in room run | Skip equal vectors | Changed samples / 4.97 s | Changes/s | Accepted presents/s in complete enclosed intervals |
| ---: | --- | ---: | ---: | ---: |
| 98 s | Off | 45 | 9.06 | 9.19 |
| 120 s | On | 44 | 8.86 | 9.13 |
| 141 s | On | 46 | 9.26 | 9.13 |
| 162 s | Off | 43 | 8.66 | 8.98 |

The room was visible at 80 and 170 s, and the character's pose differed. The four-block result was ready at 172.1 s. The full qualifying intervals gave 341 presents in 38.50 s off (8.86 FPS) and 346 in 38.26 s on (9.04 FPS). The pair differences were +0.03 and +0.34 FPS. The enabled path examined 18,635 MiB. The visual samples ran during the comparison, so these numbers include the cost of that check. The earlier eight-block result stays excluded.

With the game window ID on the correct X11 display, use `python3 benchmarks/window_activity.py "$window" --seconds 5 --rate 30`. Choose a sample rate above the frame rate you want to check. FFmpeg and ffprobe need X11 capture support. The reported changes/s applies only to the sampled crop and time span.
