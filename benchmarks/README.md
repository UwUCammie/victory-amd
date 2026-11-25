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
| 16 KiB readbacks | 752 | 74.31 | 10.12 | 4,829 |
| 4 KiB readbacks | 591 | 73.67 | 8.02 | 4,875 |
| 16 KiB, levels on demand | 624 | 73.76 | 8.46 | 4,905 |
| 16 KiB, Vulkan descriptor buffers | 693 | 74.07 | 9.36 | 4,873 |
| 16 KiB, host-read and viewport sampling | 655 | 73.82 | 8.87 | 4,854 |
| Same sampling build, 1080p display setting | 555 | 73.22 | 7.58 | 4,870 |
| 16 KiB, consecutive GPU fetch commands joined, sampling on | 384 | 73.12 | 5.25 | 4,931 |

For the piece-size trial, the renderer used asynchronous submit, two queues, parallel refresh and merge, the 64-lane card compare, and a zero merge gap. The only setting changed between those three rows was `VICTORY_CARD_PIECE_KB`. The measurement branch supplies the sampler and analysis tools. The figures came from an integration build with additional changes, including [registration lookup](https://github.com/fxceless/victory-fork/pull/1142), [parallel refresh timing](https://github.com/fxceless/victory-fork/pull/1135), [descriptor bookkeeping](https://github.com/fxceless/victory-fork/pull/1128), and [relay page ordering](https://github.com/fxceless/victory-fork/pull/1066).

The first three rows use the same executable. Median copy-queue readback fell from 93.5 to 85.8 to 59.7 MB/frame as pieces got smaller. The 4 KiB copy queue took 6.3 ms/frame, versus 4.7 ms at 16 KiB. There is one run per row so far. The desktop shared the GPU, and some runs overlapped low-priority builds. [Readback PR](https://github.com/fxceless/victory-fork/pull/1164)

The two display settings both produced a 3840×2160 swapchain. The most frequently sampled viewport was 2560×1440 in both, followed by 2048×2048. The first room was visible in a capture from each run. [Display measurements](https://github.com/fxceless/victory-fork/issues/10#issuecomment-7176659252)

On-demand levels avoided 3,057 MB of logical mip backing at the final sample. The tile pool held 896 MB of heaps. Joining adjacent GPU readback commands removed about 4,152 copy commands/frame. CPU preparation and GPU waits both increased in that trial. [Mip backing](https://github.com/fxceless/victory-fork/issues/898#issuecomment-7176439226) · [Readback commands](https://github.com/fxceless/victory-fork/pull/824#issuecomment-7176776652)

## Copy-worker benchmark

From a checkout with both refs available, run the native benchmark with Python 3 and Rust. It uses the pool implementation from each revision, checks that every submitted job completed and alternates run order. The buffer-update workload uses synthetic bytes.

```sh
git fetch https://github.com/fxceless/victory-fork.git refs/pull/1172/head
python3 benchmarks/copy_pool.py 9c184b35 FETCH_HEAD
```

Eight paired trials on the 9700X gave median times of 21.40 and 11.15 ms for two callers each submitting 64 batches of 512 counter jobs. Two callers updating 1–5 KiB buffers took 7.77 and 5.13 ms. [Worker-pool PR](https://github.com/fxceless/victory-fork/pull/1172)
