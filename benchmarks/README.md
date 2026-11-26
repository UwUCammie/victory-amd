# Compare renderer changes in one launch

Build the runtime once. Choose one switch per trial. Use `VICTORY_HEAP_SYNC_ZERO_RUNS=paired` to test the descriptor scan or `VICTORY_CARD_SYNC_BATCH=paired` to test the upload and hash command order. Their fixed modes `0` and `1` remain available for separate-process controls. The live setting switches at present-report boundaries. The first four blocks run off / on / on / off. The next four reverse that order. The descriptor scan produces the same cache updates in both modes. The upload trial changes how one command list records work over independent buffers. Its counter counts buffers in groups containing two or more.

```sh
cargo build --release --locked -p victory --features victory-hle/benchmark-input
rustc --edition 2024 -O benchmarks/paired_renderer.rs -o paired_renderer
```

Launch the usual route with the same input, cache and display settings. Set `VICTORY_BENCH_WARMUP_SECONDS` to a point where a visual check has confirmed gameplay on your setup. The default is 150 seconds from the frame meter's start. Set `VICTORY_BENCH_BLOCK_SECONDS=20` for the shorter trial (default 40). Each block excludes its first complete reporting interval. Check the scene at the beginning and end of the measurement and keep captures and logs local.

After four blocks, the reporter can produce a first comparison from standard input. After eight, the same session gives four pairs. The file form checks the complete log for device or runtime failure. For the RX 7900 XT first-room route we require at least 3,000 draws per accepted present in each block.

```sh
./paired_renderer run.log --blocks 4 --min-draws 3000
./paired_renderer run.log --blocks 8 --min-draws 3000
```

The report rejects missing blocks, short measurement windows, unexpected draw counts and inactive counters. It pools accepted frames and measured time by mode and prints each pair's difference. Reversals between pairs warrant a repeat. A change to startup, shader compilation, allocator lifetime or persistent cache layout still needs a separate-process comparison.

For a descriptor predicate edit, run the portable two-test fixture first. On the 9700X it compiled and ran in 0.11 seconds. Then run the placed-heap test on a physical GPU before scheduling a title run. [Portable fixture and command](https://github.com/nicolasveilleux/victory-fork/pull/2)
