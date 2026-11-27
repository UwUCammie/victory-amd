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

## HUD layout at 1280×720

The Radeon 720p preset enables `VICTORY_UI_PLANE_720=1` on builds carrying the [interface fix](https://github.com/avatarmanz/VIctory-7900XTX/pull/295). The Series X scene output and Windows swap chain are 1280×720. The title lays out its interface on a separate 3840×2160 plane, which the compositor scales onto the scene. The preset also enables `VICTORY_UI_VIEWBOX=1` so that turning the separate plane off selects the single-plane subtitle and HUD fix.

I compared the same elements in private 1280×690 window captures on the RX 7900 XT. One line of dialogue measured 467×20 pixels at (406, 606) with the separate plane and at the same size and position in the 4K reference. The same credit measured 219×33 pixels at (898, 532) versus 218×33 at (899, 532). The Retry Checkpoint label measured 186×19 versus 186×20, both at (1056, 172). The left pause-menu panel uses 28% of the window on both. I opened, closed and reopened the menu.

With only the single-plane HUD fix, the movement hint and the bottom action bar fit. The same credit still measured 655×102 and the pause panel occupied 85% of the window. On an earlier subtitle cue, the HUD fix brought the glyphs from 278×52 at 71.0% down the frame to 92×16 at 90.1%. [Matched UI captures, aggregate measurements](https://github.com/avatarmanz/VIctory-7900XTX/issues/282#issuecomment-7196096753)

## First boot at 1280×720

Start the clock before launching Wine. Use an existing offline test prefix with the player's completed setup and settings and omit the story slot. Give each launch new empty directories for the runtime shader and pipeline cache (`VICTORY_CACHE_DIR`), vkd3d (`VKD3D_SHADER_CACHE_PATH`), Mesa (`MESA_SHADER_CACHE_DIR`), DXVK (`DXVK_STATE_CACHE_PATH`) and `XDG_CACHE_HOME`. Leave the player's normal caches and saves alone. This measures a first story launch with cold graphics caches. System file caches and the installed Wine prefix persist.

Use the [accepted-present trace](https://github.com/UwUCammie/VIctory-7900XTX/commit/cc16d08e) with `VICTORY_FRAME_TRACE=1`, Series X and `VICTORY_OUTPUT=1280x720`. Record launch and exit UTC timestamps in `launch.json` as `start_utc` and `end_utc`, the timeout in seconds as `timeout`, the initial number of story slots as `story_slots`, and the initial entry counts for `cache`, `vkd3dcache`, `mesa`, `xdg`, `dxvk` in `empty_cache_directories`. Store the timeout command's exit status in `exit-code` next to `run.log`. Mark runs interrupted by another game with `foreground-overlap` next to the metadata. Keep the logs and any scene captures local.

```sh
python3 benchmarks/cold_boot.py path/to/run path/to/launch.json --start 0 --stop 300 --expect-output 1280x720
```

The optional `--expect-output` checks the host swap-chain size at creation and on each subsequent resize. For a run using the 720p UI fix, add `--expect-interface 3840x2160`. This requires the loader to confirm that it applied the separate interface plane before the first accepted present. A failed setup can also print the requested dimensions.

Add `--stalls 5` to list the five longest gaps in a saved run, including gaps at the start and end of the window. Each row counts the renderer’s first compute-drop notices inside that gap and gives the elapsed seconds from the start of the gap to its earliest notice. A pipeline can drop further dispatches silently after its first notice. Use `--compute-gap-ms 9500` to count all gaps of at least 9.5 seconds, their total duration, and how many contain a compute-drop notice. The overlap describes timing only.

The two stock 720p launches each had five gaps of at least ten seconds, all between seconds 27 and 83 of the first story boot. The earliest compute-drop notice in each gap came 9.85–10.15 seconds after the preceding present. The first gap of each boot contained 243 and 235 first-drop notices respectively. The compute wait budget is shared across a frame, so those counts can bunch together when the budget runs out. Measuring the duration of an individual pipeline build requires its own start and finish timestamps.

In a separate experiment, I changed the frame-wide compute budget and kept the per-pipeline age limit at ten seconds. All three launches used the same release executable, RX 7900 XT, RADV 26.3.1 and GE vkd3d-proton `cae8353e`. Timing covers the first 300 seconds from starting Wine, with the same inputs, five empty graphics caches and no story save.

| Frame budget | Presents | Average FPS | P99 gap | Longest gap | Gaps over 1 s | Time in gaps over 100 ms | First compute-drop notices |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 s | 4,268 | 14.23 | 292 ms | 11.18 s | 31 | 141.43 s | 337 |
| 4 s | 4,099 | 13.66 | 479 ms | 5.27 s | 39 | 144.84 s | 479 |
| 2 s | 4,511 | 15.04 | 1,514 ms | 3.39 s | 48 | 134.35 s | 552 |

Both shorter budgets reduced the worst hold and produced more holds over one second and more first-drop notices. The four-second trial averaged fewer presents than the ten-second run. Faces and skin were visible in later shots in all three launches. Several cuts differed at fixed timestamps and one run per budget leaves visual equivalence and the FPS differences unconfirmed. See the [experiment source](https://github.com/UwUCammie/victory-amd/commit/a8343791).

For a runtime with `VICTORY_FRAME_HEALTH`, run `python3 benchmarks/frame_health.py --seconds 270 OFF.csv ON.csv` to get aggregate pipeline misses and texture or memory peaks from the same duration after each first accepted present. The helper rejects files that end before that duration. The 270-second window leaves room for buffered CSV rows near timeout. Keep the individual rows local and use the accepted-present trace for FPS from launch.

On Linux, `cold_launch.py` creates the directories and records the metadata for a direct Wine launch. Use a dedicated offline prefix, export the settings from `radv_first_room.env` and pass the same timed input to each run. Supply a fresh output directory for every trial. The installed Wine prefix needs a working Z: mapping. For example, from the installed game's working directory:

```sh
python3 "$bench/cold_launch.py" --run "$results/trial-1" --profile "$player_data" -- \
  bwrap --unshare-net --dev-bind / / -- wine "$runtime" run "$title" --execute --console series-x
python3 "$bench/cold_boot.py" "$results/trial-1" "$results/trial-1/launch.json"
```

The denominator is the full interval from launcher start. A frame counts at the start boundary and is excluded at the end. Time before the first present, long freezes and time after the last frame all stay in the window. The longest hold and nearest-rank p95/p99 describe the positive gaps clipped to the window, including both edges. The time in holds over 100 ms includes the full length of those holds. Count a walking interval separately once input and movement are confirmed. The first accepted present can still be a blank screen.

On a Ryzen 7 9700X and RX 7900 XT (RADV 26.3.1, Wine 11.22, vkd3d-proton GE build `cae8353e`), the initial completed run produced **4,063 presents in 300 seconds (13.54 FPS)**, including loading, the opening sequence and the prison cell. The first present was at 2.54 s, p99 was 268 ms, and the longest gap was 11.33 s. There were 27 holds over one second, including the initial wait. Holds over 100 ms took 138.90 s. The compute pipeline wait reached its ten-second frame budget in six distinct title frames. The settled prison-cell view averaged 24.23 FPS over seconds 220–300; movement was not verified in that interval.

### Cold control and compute-at-creation comparison

Both trials used the same binary, key sequence and protected compute wait. The clock started before Wine; each trial ran for 308 seconds. The second measurement window includes standing at the cell window, walking and turning. Identical input timing led to different final camera positions. The first visible response to the directional input was captured by 252.4 seconds after launching in both runs. Earlier stills show the character in the cell, so this is an upper bound on when control became available.

| Pipeline scheduling | First 300 s | Seconds 220–295, movement | p99, first 300 s | Longest hold | Time in holds over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default, ten general workers | 4,241 / 300 = 14.14 FPS | 1,923 / 75 = 25.64 FPS | 252.8 ms | 11.28 s | 141.70 s |
| Start every waiting compute pipeline at creation | 2,394 / 300 = 7.98 FPS | 865 / 75 = 11.53 FPS | 693.3 ms | 11.17 s | 220.86 s |

The default lost the character's facial skin in the diner dialogue and again in the cell, with eyes, hair and teeth still visible. The head blend-shape pipeline identified in the compute-wait patch was first bound at 49.49 s, its dispatch timed out at 59.50 s and the host pipeline was ready at 84.63 s. The earlier control with no late walking input showed the same missing face at the same spoken line. With [compute compilation at creation](https://github.com/UwUCammie/VIctory-7900XTX/commit/1bf28084), the host pipeline was ready at 44.17 s ahead of its first bind at 55.15 s; the face was visible at that line and the character had skin in the cell. The cost of queueing all that work persisted into gameplay. One run per configuration; the faster control fails the visual check.

With six general workers the same route gave 13.25 FPS from launch and 23.91 FPS in the movement window; the face was still missing. A second run starting every compute build at creation again drew the face, at 9.19 FPS from launch and 14.63 FPS over the movement window.

Limiting speculative work to compute shaders of at most 2,048 bytes gave **13.06 FPS** over the whole five minutes (3,919 frames) and **23.96 FPS** over the movement window (1,797 frames). The face pipeline was ready at 3.25 s and first bound at 28.58 s. Both diner faces had skin, and the player character still had skin after turning in the cell. P99 was 475 ms. There were 30 waits longer than one second and the longest was 11.12 s. Compared with starting all compute builds, this kept the visible face and cut time in holds over 100 ms from 207–221 s to 152 s. The default missing-face control spent 142 s in those holds.

At 1,024 bytes the first clean trial gave **14.10 FPS from launch** (4,230 / 300 s) and **25.01 FPS in the movement window** (1,876 / 75 s). The diner and cell character both had facial skin. The face pipeline was ready at 3.59 s and first bound at 28.98 s. P99 was 281 ms; 27 holds exceeded one second, the longest was 11.17 s, and 138.97 s were spent in holds over 100 ms.

The RX 7900 XT desktop preset uses the 1,024-byte limit and sources `radv_first_room.env` followed by `radv_720p.env` and uses the [size-limited build](https://github.com/UwUCammie/VIctory-7900XTX/commit/ae742781) with 1280×720 output support. The desktop retains its ordinary graphics caches. The benchmark gives each launch new ones.

The follow-up 2 KiB run measured 13.18 FPS over the first 300 s and 24.15 FPS in the movement window. Faces were visible in the diner and the cell. The repeat of the 1 KiB launch stayed in the opening cinematic and credits during seconds 220–295. Its **12.68 FPS** across the full five minutes is a valid cold-launch observation; that late interval cannot verify a second walking score. Timed skip inputs can take a different route when loading stalls shift the cutscenes.

[Linux branch PR #5](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/5) carries the size limit. Starting compilation only when a recording thread first bound the compute pipeline still lost the skin (12.65 FPS from launch, 23.69 FPS in the movement window). Turning off landing-echo detection on its own also left the face missing on this cold route (12.89 / 23.25 FPS).

The six holds over ten seconds in the 1 KiB trial coincided with frames that exhausted the compute wait budget. The first bind of 1,051 distinct compute shaders appeared in the log. Of those, 314 reported a dropped dispatch while waiting. None of the 52 shaders of 1 KiB or less reported one. This count is per shader because the runtime logs its first drop only.

A [reverse-use index in the shader translator](https://github.com/UwUCammie/VIctory-7900XTX/commit/1a90bf03) produced identical bytecode and metadata or the same translation error for a 256-input sample. A Windows build from a shared Cargo target directory still contained the previous translator. Its matching PDB recorded the baseline checksum for the changed source file. The 13.05 FPS from launch and 24.27 FPS while moving are additional control measurements. The two native comparison binaries did compile their respective translator sources.

Across all 26,503 local inputs, four native processes reduced end-to-end corpus translation time from 201.81 to 105.50 s. All 26,308 translations matched in DXIL and metadata, and the 195 errors matched. In four alternating runs per build on the 256-input sample, the median sum of individual translation durations fell from 3.49 to 2.96 s. [Linux branch PR #6](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/6)

With the native UI plane active at 1280×720, the index gave 3,869 presents across the first 300 seconds from an empty-cache launch (12.90 FPS). The two stock controls gave 3,298 and 3,954 (10.99 and 13.18 FPS). The candidate had a 493 ms P99 gap, a longest gap of 11.42 seconds and 33 gaps over one second. It spent 159.7 seconds in gaps over 100 ms, compared with 177.0 and 154.1 seconds for the controls. All three used the same scripted inputs and five empty caches. The candidate's opening world was black in the 70, 85 and 100 s captures, then visible at 115 s.

For slow compute pipelines recorded by both builds, I matched the first dropped dispatch and subsequent host completion for the same shader. I included only completions at least two seconds before each run's persisted timing snapshot. Against the first and second controls, respectively, 177 and 178 shaders qualified. The candidate's median paired change in drop-to-completion time was **+4.63 s** and **+5.30 s**. That interval includes queueing and host compilation. The offline translation speedup did not shorten the wait in this cold run.

An isolated Windows build with the new translator matched the recorded checksums of all 166 runtime source files. Another project started an eight-way native build 167 seconds into its first 720p trial. Under that load the run gave 8.15 FPS from launch and 12.16 FPS during movement. The entire movement interval overlapped the build. This trial is excluded from controlled gameplay comparisons. The desktop still uses the previous translator. The GPU queue now yields to parallel native builds as well as other foreground games. On Linux, `competing_build.py` returns success when an explicit Make/Ninja job count or concurrent compiler processes indicate a parallel build. Mark the affected launch with `validation-overlap` before retrying.

For Windows cross-builds from multiple worktrees, use a separate Cargo target directory for each candidate. Before testing, compare the executable's CodeView GUID and age with its PDB, then check the recorded Rust source hashes against the intended checkout. Pass a changed source path to require its presence. This takes well under a second on this system and caught the stale translator before another five-minute trial.

```sh
python3 benchmarks/verify_pdb_sources.py "$checkout" "$build/victory.exe" "$build/victory.pdb" crates/victory-shader/src/emit/lower.rs
```

### Texture copy order at 720p

The 308-second archived opening reported successful texture readbacks, so both tiling and detiling are relevant. I compared the AMD branch at `830dc191` with the combined texture-copy change at `acbaed74`. Each pair used the same input and destination allocations. The figures are median Linux thread CPU microseconds per copy on a Ryzen 7 9700X over 15 alternating pairs. Only mip zero was timed. Five mip levels per surface were checked byte for byte, including padding.

| Surface | Original detile | Combined detile | Original tile | Combined tile |
| --- | ---: | ---: | ---: | ---: |
| 1280×720 RGBA, 64 KiB S | 145.31 | 126.74 | 179.00 | 94.15 |
| 1280×720, 16-byte 4×4 blocks, 64 KiB S | 42.53 | 34.86 | 37.27 | 22.15 |
| 1279×719 single channel, 4 KiB S | 40.44 | 33.92 | 126.84 | 32.36 |
| 32×32 RGBA, 64 KiB S | 0.289 | 0.367 | 0.314 | 0.364 |

The upstream fixed-width copy loop alone took 281.0 µs to tile the 720p RGBA surface, up from 190.0 µs in that pair. Visiting one destination block at a time brought that down to 91.7 µs from 287.6 µs in a separate direct comparison. The 32×32 regression remains in the combined change. An independent trial that cached the run width brought that small detile from 0.356 to 0.217 µs, but the compressed 720p detile went from 32.50 to 36.45 µs. I left the cached-width trial out of the combined branch. These are synthetic copy timings. [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/12) · [Upstream follow-up](https://github.com/brainbudt/VIctory-7900XTX/pull/1) · [Cached-width trial](https://github.com/UwUCammie/VIctory-7900XTX/commit/248ac514)

To repeat the combined comparison from this benchmark checkout on 64-bit Linux, set `port` to a VIctory checkout containing the two commits. The harness emits the case, direction, pair, version, copy count and elapsed thread CPU nanoseconds. Divide by the copy count before taking each median.

```sh
trial=$(mktemp -d)
cp benchmarks/texture_copy.rs "$trial/main.rs"
git -C "$port" show 830dc191:crates/victory-formats/src/texture.rs > "$trial/reference.rs"
git -C "$port" show acbaed74:crates/victory-formats/src/texture.rs > "$trial/candidate.rs"
rustc --edition 2024 -O "$trial/main.rs" -o "$trial/texture-copy"
"$trial/texture-copy"
```

### Classifying shader memory writes after translation

After host translation the runtime classifies writes to buffers and writes through raw addresses. Both checks decoded the same GFX10 program. I tested a version that shares one decode between them. It produced the same pair of flags for every one of 26,503 local containers. Of those, 4,231 could write buffers and none reported raw-address writes. A separate Windows test under Wine 11.22 covered a synthetic raw write and the conservative fallback for missing and truncated programs.

I matched 2,862 of 2,865 distinct completed translations in a 308-second opening to the local corpus. In a native Linux release harness I timed only the classifiers on the program vectors already in memory. Median thread CPU time for the whole matched set was 2.182 s for the original and 1.136 s with one decode. The new path was quicker in all eight alternating pairs. The 720p cold queue tests gameplay separately. [AMD branch PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/11)

### Finding ambient passes during shader registration

Each new compute shader is classified while the shader table is locked. I compared the current byte-window search with the workspace's existing substring search. They returned the same role for all 26,503 local containers (245,181,656 bytes), including all eight positive matches.

For the timing I matched the first-bind records from one 308-second opening to the local corpus by content hash. I could recover 1,056 of the 1,091 distinct bound compute containers, totaling 23,282,628 bytes. File reads, hashing and result verification finished before the timer started. Across 12 alternating pairs with the inputs in memory, the median thread CPU time for the full set was 72.12 ms for the byte-window search and 3.21 ms for the substring search. The latter was quicker in every pair. This measures one step of shader registration. The three Windows ambient tests passed under Wine 11.22. [AMD branch PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/10)

### Streaming the shader cache key

The shader cache joins a 32-byte build fingerprint to each container before hashing it. I tried feeding those two slices to BLAKE3 separately. One local opening supplied 2,795 distinct input sizes. With synthetic buffers of those sizes, one pass avoided copying 40,097,932 bytes and produced identical keys for every input.

In 12 alternating pairs on Linux, hashing the joined buffers took a median 18.28 ms of thread CPU time for the whole pass. Feeding the slices separately took 18.47 ms and was faster in two pairs. Both paths used the same cache-key implementation. This times key construction alone. Four Windows shader-cache tests and seven pipeline-cache tests passed under Wine, including a hit on an entry keyed by the old writer. I kept the experiment off the desktop build. [Trial patch](https://github.com/UwUCammie/VIctory-7900XTX/commit/278157c82bbff0c07d1f934bef8bb5b882ac7ee0)

### Withdrawn cold-launch timings from November 26

I matched a second native renderer’s session times against the launcher metadata after finding two of its processes with the RX 7900 XT render node open. It renamed its main thread to `render`, which the foreground guard missed. The overlap started during some launches and was already in progress for others.

| Affected measurements | Status |
| --- | --- |
| 720p HUD fix, 12-minute opening and prison movement | Withdraw the full-run and both window averages, including 17.52 and 24.77 FPS. |
| Separate UI plane, first 300 seconds | Withdraw the 14.01 FPS reference. UI pixel measurements are independent of this timing. |
| Cached shader reuse, candidate and fresh control | Withdraw 9.42 and 7.49 FPS and their stall comparisons. |
| Indexed shader values | Withdraw 8.33 FPS as a game timing. The separately tested shader outputs and translation workload have their own results. |
| Stock and 16.667 ms title timer | Withdraw the FPS comparison for both settings. The title reported the configured intervals. |

On Linux, `competing_gpu.py --executable OTHER_GAME` recognizes an independent game by its executable even when it renames its threads. For other graphics jobs in a known separate cgroup, add `--group OTHER_JOBS.slice --node /dev/dri/renderD128` with the benchmark GPU's render node. It returns zero while a matching game is running or a process in that cgroup holds that node. Use it before launch and throughout the measured run. The benchmark's own cgroup must be outside the selected group. Some job launchers pass their idle render handle to every child. On a dedicated GPU, `--ignore-inherited-idle` allows a client shared with the launcher when it has zero resident VRAM and every reported engine counter is zero. A separate client on the same GPU still blocks the test. Use `--explain` to log the blocking PID.

The cache candidate still wrote 2,710 shader entries totaling 170,699,798 bytes during its run. `compute_lag.py` can match first-drop warnings to successful translation messages in an existing log. The contaminated runs establish neither a normal queue delay nor a change in rendering performance. The desktop retains the separate 720p interface plane and the stock timer. [UI fix](https://github.com/avatarmanz/VIctory-7900XTX/pull/295) · [Cache change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/8) · [Translator change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/6)

### First clean cold run with the separate UI plane

With the stock timer and the 1 KiB early-compute limit, the RX 7900 XT presented 3,298 frames in the first 300.00 seconds after launch (10.99 FPS). First present took 2.19 s. P95 was 89.55 ms, P99 was 1.743 s, and the longest gap was 11.187 s. There were 36 gaps over a second; gaps over 100 ms accounted for 176.97 s of the window, including its edges. No story slot or graphics-cache entries were present at launch. The loader applied the separate 3840×2160 interface before the first present, and the host swap chain was 1280×720. The capture shows the opening diner during the timed window. This is one clean reference with the corrected interface. The previous attempt yielded to an unrelated parallel build and is excluded.

With the same keys, output configuration and five empty caches, the shader cache reuse trial presented 2,403 frames in 300.00 s (8.01 FPS). First present took 2.82 s, P95 was 98.45 ms, P99 was 2.825 s and the longest gap was 11.407 s. Gaps over 100 ms occupied 206.25 s. At 205 s the two runs were at different shots, so this one pair measures the full first-boot experience and cannot isolate a rendering cost for the same scene. Cache reuse remains outside the desktop preset. [Cache reuse trial](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/8)

For quicker feedback while the full cold run continues, add `--progress --start 60 --stop 120` to the `cold_boot.py` command. It returns a partial report once the log contains a present at or beyond the end of that window. A running observation carries `"provisional": true`; the normal report still requires a complete run. Both paths check the empty caches, new story, overlap markers and requested display sizes. Minute two of the two stock boots ran at 0.83 and 0.88 FPS. Both spent over 58 of that minute's 60 seconds in gaps over 100 ms. This makes minute two a short diagnostic for work on opening stalls. The goal score still covers the full 300 seconds from launch.

### When work began on late compute pipelines

The runtime records elapsed worker build time for pipelines that took at least one second. On a clean launch I matched the first dropped compute dispatch and the first successful host pipeline log to that saved duration. Subtracting it from the host completion time estimates when work began. Only keys present in the cold run's slow-build snapshot count, and the completion must precede the snapshot by at least two seconds. The saved time is a maximum for a key, in whole milliseconds. These are estimates from the full 308-second process log, not direct measurements of queue residence.

| Cold 720p run | First-drop shaders | Matched to slow builds | Median worker build | Median estimated start after drop | Estimated start more than 10 s after drop |
|---|---:|---:|---:|---:|---:|
| Separate UI control | 344 | 182 | 2.62 s | 23.79 s | 142 |
| Shader cache reuse | 398 | 198 | 3.74 s | 33.85 s | 161 |
| Reflection binary, pass off | 339 | 188 | 2.59 s | 22.77 s | 146 |

The delay before the measured build merits testing separately from the cost inside the driver and translator. To repeat this on local runs, install the Python `blake3` package and run `python3 benchmarks/compute_build_time.py RUN_DIR METADATA_DIR/launch.json`. The report emits aggregate counts and timings.

For the first and second stock runs, the translation-complete message fell inside the estimated worker interval for all 182 and 183 matched slow builds. The median time from that message to successful host pipeline creation was 1.70 s and 1.66 s. The median share of each worker interval spent after translation was 65.2% and 65.5%. That interval includes host setup, pipeline library access, driver compilation and time descheduled. The logs cannot apportion it between those costs.

Binding often gave very little advance notice. In the first cold control, 307 of 344 distinct compute shaders with a first-drop notice were logged as bound less than one millisecond before that notice. In the second control it was 283 of 306. The median signed time between the log records was 24 and 18 microseconds respectively. Only four and two first binds were at least ten seconds earlier. Two first-drop messages in the first run even preceded the corresponding first-bind message. These are timestamp differences between messages from multiple threads; they measure the opportunity visible at the first-bind hook, not the execution time of either call. To reproduce from a local log, run `python3 benchmarks/compute_lag.py RUN_DIR/run.log --early-bytes 1024`.

The [wait-priority experiment](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/17) records whether a worker has entered the build at the first dropped dispatch. With priority off, 370 of 376 distinct first-drop shaders still had no worker start recorded; six had started. The five-minute cold score was 2,643 presents (8.81 FPS), P99 2.39 s, and 197.03 s in gaps over 100 ms. Drop counts cover the complete 308-second process. The early report for minute two matched the final report for that minute exactly, including its 18 accepted presents and 59.67 s in gaps over 100 ms.

With priority on, the same verified binary delivered 2,439 presents in 300 s (8.13 FPS). P99 was 2.69 s and the worst gap was 10.55 s, against 2.39 s and 11.29 s with priority off. Gaps over 100 ms occupied 210.13 s with it on and 197.03 s with it off. An actual promotion was logged in the on run. Of 326 distinct first-drop shaders, 318 had yet to start at the worker. For the 293 shaders with both a first-drop notice and a translation completion in each process log, the signed time from first drop to translation completion fell for 75. The median of the per-shader changes was **2.49 s longer** with priority on. The two captures differed at 70 and 205 s. Some world scenery was visible earlier with priority on, but this pair gave no first-boot speedup. Two earlier on attempts yielded to a separate GPU client and are excluded.

Among first-drop notices that reported at least one second actually spent waiting, 16 of 18 shaders had no worker start with priority off. With priority on, all five had a worker start. All 16 previously unstarted shaders were bound, translated and logged a host pipeline in the priority-on run. None of those 16 logged a dropped dispatch there. These counts cover each complete process log. The full five-minute FPS result above still favored priority off.

### Root descriptor slot lookup

The submission profile included samples in SipHash, so I tested the per-command-list root SRV and UAV cache shape with the renderer's existing address hasher. The fixture uses aligned synthetic addresses over five heaps and covers both biased and ordinary slots. It clears, populates and repeatedly looks up entries just as a list does. Both maps returned the same accumulated slot values in all 21 pairs.

On the Ryzen 7 9700X, seven alternating native release pairs per size gave median times per list of 2.45 → 0.75 µs for 32 keys, 19.31 → 5.64 µs for 256, and 159.07 → 47.27 µs for 2,048. Each pair favored the address hasher. The fixture measures map operations and excludes the driver and rendering. Run `python benchmarks/root_slot_hash.py /path/to/victory` with a Rust toolchain to reproduce it.

The published fixture's second run gave 2.08 → 0.81 µs, 16.52 → 5.60 µs, and 134.81 → 46.86 µs. All 21 pairs favored the address hasher again. The Windows MSVC check passed on the PR head. [Root slot cache change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/28)

### Combined CPU changes from the first cold boot

I compared the native 720p interface build with the same build carrying the command-signature cache, root-view hash, reverse byte scan, and streamed relay flags. Runtime settings and scripted inputs matched. Both started with five empty graphics caches on the RX 7900 XT with GE vkd3d-proton `cae8353ed7959c4`. The executable and rendering source checks were verified for each arm.

| First 300 seconds | Presents | Average FPS | P99 gap | Longest gap | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Control | 2,589 | 8.63 | 2,438 ms | 11.40 s | 198.69 s |
| Combined | 2,974 | 9.91 | 539 ms | 11.55 s | 178.57 s |

Both showed a very dark sample at 100 seconds and later returned to visible scenes. At 160 seconds the control was still dark while the candidate showed the street. The later captures also hit different shots, so this one pair leaves both the visual comparison and the performance gain open to repeat. [Combined test branch](https://github.com/UwUCammie/VIctory-7900XTX/commit/1b07596f)

In the reverse-order repeat, the combined build delivered 3,147 presents in the first 300 seconds (10.49 FPS), with a 592 ms P99, an 11.20 s longest gap and 180.27 seconds in gaps over 100 ms. The matching stock run stopped advancing after about 113 seconds and Wine exited during the scheduled window. A core dump was registered at about 185 seconds. This incomplete run has no 300-second score. The first combined attempt was also excluded after a concurrent build started. The stock retry uses five fresh caches.

The stock retry then delivered 2,651 presents (8.84 FPS), with a 1,840 ms P99, an 11.39 s longest gap and 199.23 seconds in gaps over 100 ms. There were 31 gaps over one second on stock and 28 on the combined build. Both runs showed a face in the car and reached the same couch shot by the 255 s capture. At 85 and 100 s, the stock capture had subtitles over a black view while the combined capture showed the exterior. Later shots still differed. Across both clean pairs, stock accepted 5,240 presents in 600 s (8.73 FPS) and the combined build accepted 6,121 (10.20 FPS). The two run orders favor the combination on this five-minute workload. The timing does not isolate one optimization or compare identical shots.

Both 255 s and 265 s captures show the same couch view. In that ten-second window the stock run accepted 157 presents and the combined run accepted 173. The combined build had fewer gaps over 100 ms (4 versus 11) and a longer single worst gap (2.84 versus 2.26 s). This short check brackets a similar view and does not replace the full startup measurement.

Stock recorded 22 gaps of at least 9.5 seconds across the two clean runs. The combined build recorded 18. There was a compute-dispatch drop notice inside 19 of the 22 stock gaps and 16 of the 18 combined gaps. The threshold selects holds near the configured ten-second compute wait. A log notice in the same gap does not establish which thread was holding the next present. These gaps persisted after the CPU changes.

I used the same combined executable as the control for a second experiment that adds only the relay range hash and the deferred slow-history lookup. In its third clean run, that control accepted 2,314 presents in 300 seconds (7.71 FPS), with a 2,589 ms P99 and an 11.40 s longest gap. The executable hash, loaded driver, runtime flags and scripted input match the earlier 9.91 and 10.49 FPS runs of that build. This spread is large enough to obscure a small CPU change in one pair.

The first three new candidate attempts yielded to other builds. A fourth ended at about 20 seconds on its own, with process exit code 0 and no device-loss marker. I excluded all four attempts from the five-minute comparison. The candidate executable and PDB matched all 168 checked sources. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/1cb9c955)

Three later attempts also yielded. The longest of those ran for about 244 seconds before a competing build started. Another yielded when a different client took the render device. Each retry started with five newly empty caches. Attempt eight completed with no overlapping render client or build. Both scored runs used GE vkd3d-proton `cae8353ed7959c4`, the same runtime flags, and the same scripted input on the RX 7900 XT.

| First 300 seconds | Presents | Average FPS | P99 gap | Longest gap | Gaps over 1 s | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined, repeated control | 2,314 | 7.71 | 2,589 ms | 11.40 s | 29 | 208.71 s |
| Combined plus relay hash and deferred slow history | 2,451 | 8.17 | 993 ms | 11.39 s | 24 | 199.97 s |

The candidate counted 137 more presents and 8.73 fewer seconds in gaps over 100 ms in this pair. Both controls with the same executable and settings from the earlier run orders reached higher averages than this candidate (9.91 and 10.49 FPS). Both scored runs showed faces and visible scenes later, and the candidate reached a different indoor scene by the end. They had black or underlit samples at different times, and the candidate also had washed-out samples. The roughly eleven-second stalls persisted. This pair leaves the separate contribution of either change and any effect on rendering unresolved. The gameplay default stays on the existing build.

### Descriptor and pipeline wait trials from cold story boot

The Wine descriptor build carries the wide shadow-range scan and the deferred COM-reference acquisition together. The only source changes from the two stock repeats are in `shadow.rs` and `descriptor/host.rs`. All three scored launches used the same 1280×720 output, runtime flags, timed input and GE vkd3d-proton `cae8353ed7959c4` on the RX 7900 XT. Their five graphics caches and story slots started empty. Two candidate attempts yielded to other render clients or builds before the third completed.

| First 300 seconds | Presents | Average FPS | P99 gap | Longest gap | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock 1 | 2,589 | 8.63 | 2,438 ms | 11.40 s | 198.69 s |
| Stock 2 | 2,651 | 8.84 | 1,840 ms | 11.39 s | 199.23 s |
| Wine descriptor build | 2,245 | 7.48 | 2,988 ms | 11.41 s | 211.27 s |

The candidate had black samples at 85, 100 and 130 seconds and showed skin in the car and people in the room later. The stock comparison also had very dark samples and reached different shots. This cold run fell below both stock timings. An isolated comparison is still needed to attribute the difference to either change. The gameplay default is unchanged. [Tested integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/5fb3cc2d) · [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/20)

The per-pipeline completion wait experiment separately used the same 720p loader files, runtime flags, GE driver, and input as those stock runs. It accepted 2,171 presents in 300 seconds (7.24 FPS), with a 3,330 ms P99, 11.54 s longest gap and 211.51 seconds in gaps over 100 ms. There were 12 gaps of at least 9.5 seconds (129.95 seconds total), and 11 contained a first compute-drop notice. Each stock launch recorded 11 such gaps (116.18 and 116.35 seconds), with compute notices in 10 and nine respectively. The candidate showed black samples in the opening and skin in the car later. The runs hit different shots. This launch favors the existing gameplay wait settings, with one candidate observation. [Tested integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/a8c1dc73) · [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/21)

The immutable depth-plane SRV build accepted 2,034 presents in the first 300 seconds (6.78 FPS), with a 3,056 ms P99, an 11.25 s longest gap, and 213.73 s in gaps over 100 ms. Thirteen gaps were at least 9.5 s (137.14 s total), and twelve contained a first compute-drop notice. The two stock launches above accepted 2,589 and 2,651 presents (8.63 and 8.84 FPS). All three used the same timed input, five empty graphics caches, empty story slots, the GE vkd3d-proton build `cae8353ed7959c4`, 1280×720 output, and byte-identical 4K interface loader sources. The candidate used the same runner's base renderer flags. Its older metadata layout omitted the flag and executable digests. The loaded driver is confirmed in its launch log, and the staged executable and PDB matched 168 source checksums before launch. Two earlier attempts did not complete a clean window.

The completed candidate reached the car and a later indoor scene with faces visible. The samples are sparse and fall at different cuts. This run shows a lower cold average and more long waits; the sample does not establish a flicker or missing-skin change. [Tested integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/a294b3bd) · [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/22)

The texture detile retry and first-upload guard candidate accepted 1,711 presents in 300 seconds (5.70 FPS), with a 5,529 ms P99, 13.16 s longest gap and 230.66 s in gaps over 100 ms. Twelve gaps reached 9.5 s, and ten contained a first compute-drop notice. The comparison verified the same timed input, runtime flags, GE vkd3d-proton, and distinct candidate and control executables. The candidate showed washed-out frames during the opening and faces in the car and room later. Those sparse samples do not establish a rendering change. The patch has separate fixture coverage for incomplete detiles and unmapped first uploads. This launch did not improve the 720p cold timing. [Tested integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/9ed0d52e) · [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/48)

In a separate depth-plane readback test, the first list stayed pending while a second twin with complementary depth classes supplied 255 or 256 later lists. On stock `830dc191`, all 16 pixels were correct at 255 and all 16 came from the other twin at 256. The immutable-view branch returned the original pattern at both counts. Both Windows MSVC binaries ran under Wine 11.22, with GE vkd3d-proton `cae8353ed7959c4` and the physical RX 7900 XT on RADV 26.3.1. Their PDBs matched 106 runtime source checksums each. This reproduces the descriptor lifetime bug on Radeon. It does not attribute the reported live flicker to the ring. [Regression and AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/22#issuecomment-7209943511)

### Live quad translation with the reflection clamp enabled

I compared the same reflection build with and without the live-quad translator change and its unwind fix on the RX 7900 XT. Both launches enabled the reflection clamp, rendered at 1280×720 with the same interface loader bytes, and started with five empty graphics caches and no story slots. They used the same timed input and the loaded GE vkd3d-proton build `cae8353ed7959c4`. Each staged binary and PDB matched 168 runtime source checksums. The control used an older manifest, so its flags were reconstructed from the same launcher. The live candidate flags were checked on the Wine process. Two interrupted candidate attempts were excluded.

| First 300 seconds | Presents | FPS | P99 gap | Longest gap | Time in gaps >100 ms |
|---|---:|---:|---:|---:|---:|
| Reflection clamp control | 2,409 | 8.03 | 921 ms | 11.39 s | 206.85 s |
| Live quads with unwind fix | 2,525 | 8.42 | 2,209 ms | 11.57 s | 208.03 s |

The candidate had ten gaps of at least 9.5 seconds, versus thirteen in the control. The average was slightly higher and the P99 gap more than doubled. This is one pair. I confirmed several matched shots in the living room. The diffuse and bright couch areas looked similar in these snapshots. The 4 Hz capture and available matches did not establish whether the reported diner flicker changed. Gameplay settings stay as before. [Candidate source](https://github.com/UwUCammie/victory-amd/commit/c5049ab8) · [Original quad work](https://github.com/avatarmanz/VIctory-7900XTX/pull/354)

### Single decode for shader write classification

The single-decode change for classifying buffer writes accepted 2,096 presents in the first 300 seconds (6.99 FPS). The two stock launches accepted 2,589 and 2,651 (8.63 and 8.84 FPS). The candidate had a 3,859 ms P99 gap and an 11.44 s longest gap, with 217.39 s spent in gaps over 100 ms. Stock P99 was 2,438 and 1,840 ms. The candidate had ten gaps of at least 9.5 s, nine with a first compute-drop notice. Sixteen overlapped launches were excluded.

The three scored launches used the same renderer flags, timed input, 1280×720 output, 4K interface loader bytes, empty story slots, five empty graphics caches, and GE vkd3d-proton `cae8353ed7959c4`. I checked the candidate's live runtime flags and distinct executable digest. Its PDB matched 168 source checksums. The early candidate samples show an exterior where the two stock runs had reached different shots. Later samples show visible faces in both the candidate and stock. This comparison does not establish a visual change or a cold-boot speedup. [AMD PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/11)

### Revised CPU fixtures

On the Ryzen 7 9700X, the [portable-only AVX2 revision](https://github.com/UwUCammie/VIctory-7900XTX/commit/9b96f866) agreed with the original outputs in the same three-way merge fixture. At 64 KiB, the median paired time changes for equal, sparse and dense inputs were −69.71%, −24.36% and −26.51% for baseline x86-64. With `-C target-cpu=x86-64-v3`, the stock loop is selected and the respective changes were 0.00%, −0.21% and −0.01%. The 31-byte measurements varied at nanosecond scale. Seven serial pairs per case.

The [revised texture snapshot](https://github.com/UwUCammie/VIctory-7900XTX/commit/1e47caee) preserves the counts-only traversal. All 420 generated cases agreed with the control. Over nine paired trials, the 40,000-slot due-list plus counts case improved by a median 34.30% (medians 320.64 and 193.73 µs). Counts alone changed by +0.17% across the paired ratios. These are CPU fixtures. The timed results here do not measure gameplay or a renderer wait.

### Descriptor heap binding

The draw-and-dispatch bind code can submit up to two heaps. I moved the short list from a vector to a stack array. A native fixture runs the exact list-building code with mock handles. For each of no heap, view only, sampler only and both heaps, it checked 10,000 updates. The retained and bound handles agreed in both versions, including their order. The control made 10,000 temporary allocations per case and the candidate made zero. The Windows MSVC compile check passed. The fixture does not time the D3D12 call or gameplay.

Run `python3 benchmarks/descriptor_heap_list.py CHECKOUT 830dc191 5633752b` with Rust 1.98.1. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/5633752b)

### Relay flags before copy-back

The relay first collected every candidate flag in a vector, then collected the flagged keys in a second vector before sorting and deduplicating them. Supplying the flags directly to the collector removes the first vector. Both revisions returned the same sorted keys in the generated cases, including duplicates and partial overlap in the existing relay tests.

Seven alternating pairs per case ran on one Ryzen 7 9700X core. All 56 favored the streamed collector. With a quarter of the flags wanted, the median times went from 1.033 to 0.865 µs at 512 flags, 11.084 to 9.793 µs at 4,096, and 41.343 to 36.426 µs at 16,384. With all 16,384 wanted, they went from 122.440 to 108.874 µs. The two existing relay tests passed under Wine in the Windows MSVC build.

From the source checkout, run `python3 /path/to/benchmarks/stream_relay_flags.py 830dc191 2b8bce96`. The fixture measures the flag collection and sort, including the removed temporary allocation.

### Relay readback range deduplication

The relay profile included samples in SipHash. I tested the readback path's set of (copy key, start, end) tuples with the renderer's existing address hash. The fixture uses aligned synthetic keys and checks that both sets admit the same number of ranges and bytes. Seven alternating pairs per case ran on core 3 of a Ryzen 7 9700X with Rust 1.98.1. All 42 pairs favored the address hash.

| Candidate tuples | Input | Random state, µs per list | Address hash, µs per list |
| ---: | --- | ---: | ---: |
| 64 | Unique | 2.566 | 0.859 |
| 512 | Unique | 19.928 | 5.793 |
| 4,096 | Unique | 184.514 | 68.536 |
| 64 | Repeated | 1.141 | 0.379 |
| 512 | Repeated | 9.098 | 2.743 |
| 4,096 | Repeated | 72.810 | 20.728 |

Each repeated input includes up to three copies of each tuple. Run `taskset -c 3 python3 benchmarks/relay_address_hash.py /path/to/victory` with a Rust toolchain. The experiment measures only set allocation, lookup, insertion and byte counting. The Windows MSVC check passed on revision `5a78284a`. Gameplay timing is pending.

### Last changed byte during copy-back

A sampled 720p run put 57 of the relay thread's 997 on-CPU samples inside the runtime image in the reverse byte scan. The AVX2 variant finds the last unequal byte from a comparison mask. It keeps the scalar tail, short-range and non-AVX2 paths.

On a Ryzen 7 9700X pinned to one core, the synthetic scan gave the following median nanoseconds over seven alternating pairs. Both versions returned the same indices. The two existing boundary tests also passed in the Windows MSVC build under Wine.

| Synthetic input | Control | AVX2 variant |
| --- | ---: | ---: |
| Identical 64 KiB | 938.30 | 571.22 |
| Difference near the start of 64 KiB | 956.60 | 568.80 |
| Difference halfway through 64 KiB | 499.47 | 309.18 |
| Difference in the last 32 bytes of 64 KiB | 3.31 | 2.30 |
| Difference in a three-byte tail | 1.35 | 1.56 |
| Single 32-byte block | 2.14 | 2.72 |

Run `python3 benchmarks/last_difference.py CHECKOUT 830dc191 8841999f` with an AVX2-capable CPU. The fixture reads both implementations from Git; it uses generated byte arrays and measures the scan in isolation.

### Shadow merge reference update

A five-second profile found 329 of 4,779 runtime-image samples in `shadow::merge_piece`. I tried copying each card byte straight into the reference after using the old reference to decide whether to update title memory. The candidate and control agreed on the changed flag and both output buffers for every generated case, including slices with different lengths. All five existing relay tests passed in the Windows MSVC build under Wine.

Seven alternating pairs per case used one core of a Ryzen 7 9700X, Rust 1.98.1 and generated buffers. The table gives the median per-pair change in elapsed time across equal, sparse and dense writes.

| Bytes merged | Default x86-64 target | x86-64-v3 target |
| ---: | ---: | ---: |
| 31 | +3.3% to +10.0% | +6.8% to +28.3% |
| 511 | +0.4% to +1.5% | −6.1% to −1.2% |
| 65,536 | +0.1% to +0.8% | −1.3% to −0.1% |

The default target got no speedup. The candidate stays out of the gameplay build. Run `python3 benchmarks/shadow_merge.py CHECKOUT 830dc191 84d6ab30` with Rust 1.98.1. To repeat the second configuration, add `--cpu x86-64-v3`. [Tested candidate](https://github.com/UwUCammie/VIctory-7900XTX/commit/84d6ab30)

### Scratch reuse across changed pieces

The piece merge already keeps initialized title and mask buffers between calls. It cleared their lengths and zero-filled them before filling them again. The adapted AMD path keeps the initialized prefix and zeroes only new space after growth. A successful read fills all title bytes. A failed read leaves the original output intact, and the merge writes every mask byte it later uses.

Native release measurements on one Ryzen 7 9700X core used seven alternating pairs for each generated case. Values are median candidate-versus-control times within each pair.

| Bytes | Sparse writes | Dense writes |
| ---: | ---: | ---: |
| 256 | −3.65% | −3.75% |
| 4,096 | −2.93% | −2.76% |
| 65,536 | −10.04% | −4.73% |

The fixture compared the merged bytes and full range of emitted writes. Thirteen Windows MSVC merge and relay tests passed in Wine, with one existing test ignored. The tested prior-output case covers shrinking, growing and a partial read that fails before the next use. Run `python3 benchmarks/merge_scratch.py CHECKOUT 830dc191 bd8b9e7e` with Rust 1.98.1. The fixture measures the piece merge with a generated read and no GPU or game. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/bd8b9e7e)

### Landing exclusions

The card landing code filtered and sorted the same set of excluded ranges for each 64 KiB piece. Sorting once per copy and reusing the gap buffer preserved every relative write span in the generated cases. The RX 7900 XT test under Wine and RADV 26.3.1 compared the batched and one-piece paths across private and mapped memory for 40 generated rounds each. It checked both the title bytes and the CPU copy. Both focused tests passed.

Seven alternating native release pairs per case ran on one Ryzen 7 9700X core. The isolated range calculation was faster in 62 of 63 pairs.

| Pieces | Excluded ranges | Control median | Reused median |
| ---: | ---: | ---: | ---: |
| 8 | 8 | 156 ns | 45 ns |
| 8 | 64 | 594 ns | 365 ns |
| 64 | 64 | 2.92 µs | 0.83 µs |
| 64 | 512 | 18.17 µs | 7.98 µs |

Run `python3 benchmarks/landing_ranges.py CHECKOUT 830dc191 9615ecdb` with Rust 1.98.1. This fixture excludes the GPU fetch and the memory writes. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/9615ecdb)

### Buffer-view alignment without a temporary backing reference

The SRV and UAV creation paths formerly cloned the backing `Arc` before checking alignment, then dropped it if they kept the same copy. The candidate borrows that copy until a distinct one is needed. The fixture made 648 checks across aligned and unaligned views, raw twins, offsets into placed memory, aliasing results and out-of-range addresses. Both selectors chose the same buffer. Three Windows MSVC descriptor tests passed on the RX 7900 XT under Wine with `VICTORY_RAW_VIEWS=0`. The physical test reached the view-relative structured slot and the PDB matched 106 source files.

| Generated selector call | Stock median | Candidate median |
| --- | ---: | ---: |
| Aligned raw | 8.74 ns | 1.37 ns |
| Aligned typed | 8.65 ns | 3.41 ns |
| Misaligned raw, separate copy returned | 16.39 ns | 8.68 ns |
| Raw, outside the backing range | 8.49 ns | 1.02 ns |

Fifteen alternating pairs per case on one Ryzen 7 9700X core. These timings cover the selection logic with a stub for the exact-copy lookup. Run `python3 benchmarks/buffer_view_shadow.py CHECKOUT 830dc191 49a89606` with Rust 1.98.1. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/49a89606)

### Selecting due texture uploads

A normal texture pass limits the due list to 4,096 slots. The control sorted every due record before taking its share. The candidate keeps the newest retries, then selects and sorts the two ends of the fresh list that can fit. It keeps the same alternating newest and oldest order. I checked 50,625 generated combinations of shuffled queues and limits against the stock implementation. Two Windows MSVC queue tests also passed under Wine, and the executable matched 106 source checksums in its PDB.

| Retried records | Fresh records | Limit | Stock median | Candidate median |
| ---: | ---: | ---: | ---: | ---: |
| 128 | 512 | 4,096 | 6.62 µs | 6.51 µs |
| 1,000 | 9,000 | 4,096 | 150.08 µs | 67.48 µs |
| 1,000 | 39,000 | 4,096 | 759.46 µs | 189.43 µs |
| 5,000 | 20,000 | 4,096 | 438.04 µs | 74.27 µs |
| 5,000 | 20,000 | 65,536 | 461.16 µs | 451.98 µs |

Run `python3 benchmarks/due_texture_order.py CHECKOUT 830dc191 81c093c2` with Rust 1.98.1. These are nine alternating pairs on one Ryzen 7 9700X core, timing the ordering call on generated records. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/81c093c2)

A follow-up measured collecting counts and the due list in one traversal. All 420 generated queue snapshots agreed. For 40,000 queued slots, the median with a due list went from 277.64 to 198.99 µs; the counts-only pass went from 92.82 to 102.72 µs. I kept this revision out of the PR while I recheck a variant that preserves the original counts-only scan. The first Windows build’s PDB showed an out-of-date dependency, so the runtime verification remains pending. [First snapshot experiment](https://github.com/UwUCammie/VIctory-7900XTX/commit/7f79d873)

### Shared-section buffer import on Wine and native Windows

The selected-adapter fixture reads generated CPU bytes back through the GPU, then writes from the GPU and validates both CPU mappings. On the RX 7900 XT with Wine 11.22 and RADV 26.3.1, the two CPU views agreed across all 320 KiB. The GPU saw zeros there, and its own 256-byte write was visible only on the GPU. That held with GE vkd3d-proton `cae8353e` and upstream `71cae091`, with `descriptor_heap` enabled.

GiovanniFadanelli independently ran both the reserved and prefilled variants on native Windows at `af245c3`. Both passed on the RX 9070 XT with driver `32.0.32029.2010`, using automatic and explicit adapter selection, and on the integrated Radeon Graphics with driver `32.0.21045.29003`. The OS, driver stack and adapters differ between these observations. The new placed-memory route needs its own check on the RX 7900 XT. [Fixture](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/23) · [Native Windows results](https://github.com/avatarmanz/VIctory-7900XTX/pull/380#issuecomment-7208330647)

### Placed Vulkan device feature probe

I built the experimental placed-memory layer with Vulkan-Headers `v1.4.328` and enabled it only through a scratch `XDG_DATA_HOME`. The RX 7900 XT on RADV reported both `memoryMapPlaced` and `memoryUnmapReserve`. A generated Vulkan device request without a placed-feature record received the two needed extensions and created a device successfully. A second request supplied both feature bits disabled. The layer passed through that request and left both fields unchanged. The AMD port also passed the Windows MSVC `cargo check -p victory`. This verifies device creation and feature negotiation. The actual mapped heap, its CPU/GPU data round trip and a timed game launch are separate checks. [AMD test branch](https://github.com/UwUCammie/VIctory-7900XTX/commit/dc1d9798) · [Upstream PR](https://github.com/avatarmanz/VIctory-7900XTX/pull/420)

### Win32 open flags on Wine 11.22

The file-cache change in Avatar #423 targets platform file I/O during startup. I opened two generated files on the benchmark host with Win32 synchronous `CreateFileW`, one with `FILE_FLAG_NO_BUFFERING`. Both aligned 4 KiB reads returned the expected bytes. `FileModeInformation` reported `0x20` and `0x28`, so Wine retained the unbuffered bit in the Windows mode. While both handles were open, the Linux descriptors had the same flags in both cases and none had `O_DIRECT` set. This narrows the Linux question to other effects of the Win32 mode. The Windows title-logo timings in the source PR are a separate workload. [Opt-in AMD branch](https://github.com/UwUCammie/VIctory-7900XTX/commit/c93361e6) · [Source PR](https://github.com/avatarmanz/VIctory-7900XTX/pull/423)

Build `file_buffering_probe.rs` for `x86_64-pc-windows-msvc` and run `python3 benchmarks/file_buffering_probe.py EXE` with the desired Wine prefix and working `Z:` mapping. The probe creates and removes its own generated files.

### Relevance of the masked write patch to cold startup

I looked for the stall that the upstream masked write patch is designed to avoid. Across 435 interval summaries in three clean 720p cold launches (the latest combined control, its relay/history candidate and the Wine descriptor candidate), every printed per-frame wait for title memory changing under shader writes was 0.0 ms at the log's one-decimal precision. This sets the priority for these cold configurations only. The saved gameplay route may expose a different workload. [Upstream patch](https://github.com/fxceless/victory-fork/commit/3221ac42)

### Chunked shadow merge

I tested the 64-byte equality check and 8-byte SWAR merge from [fxceless #1421](https://github.com/fxceless/victory-fork/pull/1421) on the AMD base. The original chunk split could miss bytes when one slice was shorter by one byte. The tested build limits all three inputs to their shared length and checks lengths on both sides of 64 bytes. All nine focused Windows MSVC tests passed under Wine.

At 64 KiB, median elapsed-time changes within seven alternating native pairs per case were:

| Target | Equal | Sparse writes | Dense writes |
| --- | ---: | ---: | ---: |
| Default x86-64 | −24.72% | +94.35% | +148.64% |
| x86-64-v3 | −46.18% | +43.46% | +139.27% |

The changed inputs regressed on both targets and the port stays outside the gameplay build. Run `python3 benchmarks/shadow_merge.py CHECKOUT 830dc191 8c6e2a3e` with Rust 1.98.1, adding `--cpu x86-64-v3` for the second target. Results are from generated buffers on one Ryzen 7 9700X core. [Tested source](https://github.com/UwUCammie/VIctory-7900XTX/commit/8c6e2a3e)

I reran the fixture on the revised upstream commit `e8fc662e`, which trims all slices to their common prefix and uses the real 32-byte `DIFF_CHUNK` with a scalar merge for changed blocks. The shared-prefix and byte-output checks passed. At 64 KiB the median paired time changes against the AMD scalar loop were:

| Target | Equal | Sparse writes | Dense writes |
| --- | ---: | ---: | ---: |
| Default x86-64 | −16.23% | +75.88% | +522.20% |
| x86-64-v3 | −44.86% | +153.44% | +800.87% |

The revised loop stayed outside the AMD gameplay build. The harness now reads each revision’s own chunk constant. To reproduce, fetch fxceless PR #1421 and pass `e8fc662e` as the candidate revision. These are synthetic merge timings without a game launch. [Revised upstream commit](https://github.com/fxceless/victory-fork/commit/e8fc662e)

A separate AVX2 experiment checks the full shared prefix for equality once, then blends changed bytes without a branch in each chunk. The synthetic output and uneven-prefix checks passed. At 64 KiB the portable build’s median time decreased by 70.67% for equal inputs, 33.70% for sparse writes, and 27.33% for dense writes. The x86-64-v3 build improved the equal case by 52.96% and took 16.90% and 17.10% longer for the changed cases. The candidate stays experimental while I check a portable-only dispatch with the original native-build loop. [AVX2 trial source](https://github.com/UwUCammie/VIctory-7900XTX/commit/7a862f0e)

### Isolated compiler thread dispatch

The two full selective-heap launches below recorded 1,559 and 1,579 successful host pipeline creations. With `VICTORY_PIPE_FIX=1` the AMD branch launches a Windows thread for each compile attempt. I measured the cost of just handing a trivial job to a fresh or reused isolated compiler on the Ryzen 7 9700X under Wine 11.22. Seven alternating pairs of 128 jobs gave median elapsed times of 17.763 ms for fresh threads and 0.390 ms for reuse, including startup. All seven pairs favored reuse. The fixture checks every reply and uses the same stack reservation and priority in both paths. These are debug fixture measurements without a driver compile. [Worker change and test command](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/24)

The fresh compiler-reuse control disabled reuse on the same 720p release executable reserved for the enabled run. It accepted 3,878 presents in the first 300 seconds (12.93 FPS), with P99 of 580 ms, a longest hold of 11.13 s, and 161.59 seconds in gaps over 100 ms. The first five minutes included menus and the opening montage, with six compiles recovered through an alternate form. The 300-second comparison starts before the first present, with five empty graphics caches and no story save.

With compiler reuse enabled, the same binary accepted 4,095 presents (13.65 FPS). P99 was 568 ms, the longest hold was 11.21 s, and 152.41 seconds were spent in gaps over 100 ms. The control and reuse runs logged 1,704 and 1,694 successful host compiles. Each recovered six compiles through an alternate form and logged zero cases that exhausted all forms. Several sampled moments showed different shots and the reuse run was dark at one 205-second sample before later indoor and montage shots rendered. The 0.72 FPS difference comes from one cold run per setting. The longest holds in both arms coincided with compute pipeline drops around the ten-second deadline.

### Direct heap requirements in the cold shader cache

Two completed 720p control runs wrote 2,840 and 2,828 translated shader stages to disk. I read the final stage bytecode from each cache entry and counted its direct heap feature bits. In the first run 2,011 stages requested the resource heap only, 745 requested both heaps and 84 requested neither. In the repeat the counts were 2,005, 738 and 85. All entries had exactly one readable feature record. For compute alone the first counts were 798, 327 and four. A graphics pipeline combines the requirements of all its stages. These counts measure where a narrower flag set is possible. [Upstream change and RX 7900 XT results](https://github.com/avatarmanz/VIctory-7900XTX/pull/58#issuecomment-7202090922)

Run `python3 benchmarks/direct_heap_features.py CACHE_DIR/shaders` on a local VSH2 cache. The reader reports aggregate counts. An unknown feature record takes the conservative two-heap path in the upstream patch.

The paired test binary with selective heap flags disabled completed a fresh cold control on the RX 7900 XT. It accepted 2,350 presents in 300 seconds (7.83 FPS), including 28 gaps over one second. P99 was 3.061 s, the longest gap was 11.469 s, and gaps over 100 ms occupied 210.34 s. The cache at exit held 1,796 resource-only stages, 666 that requested both heaps and 77 that requested neither. The control used the same 720p output and native UI plane as the enabled trial.

With selective flags enabled, the same executable accepted 2,305 presents in 300 seconds (7.68 FPS). P99 was 2.614 s, the longest gap was 11.541 s, and gaps over 100 ms occupied 209.82 s. There were 29 gaps over one second. The enabled cache contained 1,822 resource-only stages, 678 that requested both heaps and 79 that requested neither. Both launches started without a story save and with all five graphics caches empty. At 235 and 255 seconds they showed different shots of the opening montage. This pair showed no improvement in average cold-boot FPS.

The archived driver logs for 85 cold launches and 23 saved-route attempts identify the baseline as GE build `cae8353ed7959c4+`. It reports application version 3.2.0 and describes itself as 83 commits past v3.1. Earlier notes used the version in the launcher's comment. These archive counts include interrupted runs and describe driver identity only.

### Texture write-query experiment

The same release executable accepted 2,851 presents in the first 300 seconds with the texture write query optimization off (9.50 FPS) and 2,195 with it on (7.32 FPS). P99 was 2.18 s off and 3.25 s on. Gaps over 100 ms took 189.13 s off and 212.16 s on, and the longest gaps were 11.46 and 11.38 s. Both 720p launches used the same input sequence, five empty caches and no story save. The opening montage reached different shots at the same timestamps. This pair showed a worse overall cold start with the change enabled. [Texture write-query PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/19)

### vkd3d-proton on a cold opening

I ran the driver from [the Linux prison-cell report](https://github.com/avatarmanz/VIctory-7900XTX/pull/386) on the RX 7900 XT. I used the x64 DLLs from vkd3d-proton's CI package for `71cae091` in a copy of my Wine prefix, with the original DXGI DLL, release executable and input sequence. The driver log confirms the loaded revision. I kept the existing pipeline wait settings to isolate the driver change.

With five empty graphics caches and no story save, 2,702 accepted presents over the first 300 seconds gave **9.01 FPS**. The first present was at 2.53 s, P99 was 1.94 s, and the longest gap was 11.52 s. Gaps over 100 ms occupied 194.35 s, including 31 gaps over one second. The renderer logged 1,671 successful host pipelines and 378 first compute-dispatch drops during those 300 seconds. It logged zero compiles recovered through an alternate control-flow form. Two earlier clean launches of the same application on GE build `cae8353e` logged six recoveries each. A late diner close-up showed a face and the opening montage advanced. The published 23.5 FPS figure uses a standing prison-cell scene, a different card and different settings.

The fresh GE control finished with the same executable, DXGI DLL and input sequence. GE `cae8353e` accepted 2,682 presents in 300 seconds (8.94 FPS), against 2,702 (9.01 FPS) on `71cae091`. P99 was 0.81 s on GE and 1.94 s on upstream. The longest gaps were 11.45 and 11.52 s respectively. Gaps over 100 ms occupied 192.61 and 194.35 seconds. Both runs started without a story save and with five empty graphics caches. The comparable cold pair differed by 20 presents. The GE control also logged six alternate-form recoveries, against zero on upstream.

A separate run kept upstream `71cae091` and changed only the ordinary graphics pipeline wait budget from 500 ms to 2 ms. It accepted 2,068 presents in 300 seconds (6.89 FPS). P99 was 3.08 s, the longest gap was 20.22 s, and gaps over 100 ms took 212.75 s. The default-budget upstream run had 9.01 FPS, 1.94 s P99, an 11.52 s maximum and 194.35 seconds in gaps over 100 ms. The 2 ms run also showed an overbright shot at 100 s. The runs reached different shots at several checkpoints, so the capture alone does not establish which pass was missing.

For the compute-wait follow-up, both cold launches used upstream vkd3d-proton `71cae091b06571e` and a 500 ms ordinary graphics wait in the same release binary. The AMD backport's `VICTORY_COMPUTE_WAIT` switch also changes compute priority and early queue eligibility. The first 300 seconds include launch, menus and the opening sequences.

| Compute wait | Presents | Average FPS | P99 gap | Longest gap | Gaps over 1 s | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Off | 4,933 | 16.44 | 465 ms | 2.20 s | 3 | 129.50 s |
| On | 4,253 | 14.18 | 296 ms | 11.27 s | 30 | 147.11 s |

The enabled run logged 320 first compute-wait drop notices. With it off, that log path is disabled. No alternate-form recovery appeared in either run. Faces were visible in the sampled opening shots in both. The samples land at different cuts, so they do not establish whether turning the wait off preserves the skin bake throughout the scene. This was one run per setting.

I repeated the comparison with [frame-health counters](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/37) enabled in both arms. The 720p executable, driver, DXGI DLL and 500 ms graphics wait matched. Each started with five empty graphics caches and no story save.

| Compute wait | Presents in first 300 s | Average FPS | P99 gap | Longest gap | Gaps over 1 s | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Off | 3,028 | 10.09 | 587 ms | 3.84 s | 5 | 185.49 s |
| On | 2,623 | 8.74 | 2,159 ms | 11.31 s | 32 | 195.78 s |

| Compute wait | Compute recorded | Compute missed while compiling | Share missed | Draws missed while compiling |
| --- | ---: | ---: | ---: | ---: |
| Off | 4,598,280 | 427,931 | 8.51% | 331,866 |
| On | 2,441,427 | 8,240 | 0.34% | 23,793 |

The counter window covers the first 270 seconds after each first accepted present. The share uses recorded dispatches plus pipeline misses and excludes intentionally omitted ray-only dispatches. Neither run logged a terminal pipeline refusal in that window. The off capture showed a black view with subtitles at 100 seconds and reached the prison by 255 seconds. The enabled run showed an exterior in the first sample and was still in the opening montage at 285 seconds. This is one pair with different scene progress. Its counts cannot isolate the effect of waiting from the difference in work requested.

To verify a driver run locally, use `python benchmarks/cold_boot.py RUN RUN_META/launch.json --expect-vkd3d 71cae091 --expect-output 1280x720 --expect-interface 3840x2160`.

### Saved waterfront lighting at 720p

The Wine in-place heap fallback passed a matched saved-route replay with the switch on and off. With the switch on, the capability probe ran once and rejected the import. Both the page-rearrangement and imported-region counts stayed at zero, and the renderer used copied buffers. Both runs reached the glass door. The player and porch were visible at 125, 135, 145 and 155 seconds. In two earlier attempts the GPU-only fallback rejected the import but still rearranged pages. One replay hit a Wine assertion and the other an access violation. [Shared capability check and physical test](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/25)

I replayed the same saved waterfront route twice on the RX 7900 XT, with the same launch inputs and 720p executable. The first run used relay stage 2 and card steps 2. The second used relay stage 1 and card steps 0, as in the [bordersky Linux preset](https://github.com/bordersky/victory-linux). Fetch checking was enabled on both. Both arrived at the sliding glass door. The recorded intervals lasted 161 seconds and were used for visual checks.

In the final stationary view I compared 207 samples at 15 Hz for brief luminance reversals. The largest covered 0.41% of the tested rectangle in stage 2 and 0.05% in stage 1. Reviewing the adjacent frames around the peak did not reveal a protruding mesh or a whole surface disappearing. The camera and character were slightly different across runs. I could not reproduce the reported large geometry spikes on this route.

In a separate 150-second first-boot diagnostic with `VICTORY_WALLS_TRACE=1`, the exterior at 100 and 115 seconds looked dark with lit windows. During the first 145 seconds, 70 read-backs of 16 bytes and 70 of 80 bytes landed across 61 distinct frame numbers. Each width had four records between 95 and 120 seconds. All eight were finite, contained a nonzero value and differed within their width. The logger identifies transfers by size and destination only. It does not identify an exposure target or establish the cause of the bright exterior in an earlier run.

Run `python benchmarks/readback_lighting.py RUN/run.log RUN_META/launch.json --start 95 --stop 120` on a local trace to reproduce the aggregate without sharing the log.

I started three Series X runs from separate copies of the same waterfront save and the same warm application and vkd3d caches on the RX 7900 XT. All three reached the character leaning on the porch rail. The desktop preset used the indirect-light fallback at 0.8, confirmed by the renderer's radiance and resolve messages. I changed only the saved settings file's `rtDynamicShadows` value in the second run and only `VICTORY_AMBIENT=0` in the third. The wall and door stayed visible in all three. In a fixed 50×105 patch of shaded siding, each mean RGB channel was within one 8-bit level of the control at 100 seconds. This is one exterior viewpoint. The settings-file edit establishes what was requested; the log confirms the renderer fallback switch separately. These warm saved-game runs are for visual checks.

In the full desktop session, all 17 emitted warnings about unmirrored placed textures had zero backing addresses. The old warning described a lost write even on the shader-resource path. Nonzero failures now report the view type, and null textures bypass the placed-texture lookup. [Renderer PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/13)

I also replayed a short walk past the porch door with asynchronous texture uploads enabled and with only `VICTORY_TEXTURE_NO_WAIT=0` changed. Both reached a stationary view over the rail. I inspected the last 11 s of each view at 15 samples/s. The strongest brief brightness reversals in the right-hand world region were a moving bird in the default run and a waving flag in the second. I couldn't reproduce a section of the building or rail blinking out there. The camera ended at slightly different positions. In the longer desktop play log, all 1,850 indirect mesh reporting intervals displayed 0.00 records per frame rejected for exhausting a list's budget. The renderer also logged no compute-dispatch wait timeouts in that session. Neither observation explains flicker in a different room.

For fixed-camera video checks, `python3 benchmarks/flicker.py clip.mkv X Y WIDTH HEIGHT` reports the decoded frames where the largest fraction of a selected region briefly changed brightness. Use `--start-frame` and `--stop-frame` to isolate a parked camera between movements. It ignores exact repeated grayscale frames. A pixel must change by at least 24 levels on either side of a frame and return within six levels of its initial value. Inspect the neighboring frames to distinguish a surface disappearing from motion, water animation or a passing shadow. This helper needs NumPy, FFmpeg and ffprobe.

The [texture copy-back writer change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/34) completed two 187-second saved replays on the RX 7900 XT and RADV 26.3.1. Each started from a disposable copy of the same save/cache snapshot and used the same 720p release executable, relay stage 2 and card steps stage 2. The control and candidate both observed pending texture copy-back ranges. Both approached the glass door, opened it, and walked inside. The player, furniture and bright floor reflections remained visible through the final samples at 169, 177 and 182 seconds.

Over approximately 171–180 seconds I checked the same 114×76 image-space crop containing the reflective floor in each recording at 15 Hz. Across 138 distinct middle frames per run, no pixels crossed the one-frame reversal threshold in either crop. The camera headings differed inside the room, so the crops cover different floor details. The replay exercised the dependency check and did not reproduce the reported geometry flicker in these crops.

A separate pair flipped `VICTORY_AMBIENT_REFLECT` using the same UI build and saved inputs in both arms. The pass recorded at 853×480 in the enabled arm. Both runs missed the glass door and ended up in the water, with different movement and camera angles. These recordings do not establish an indoor lighting comparison. The next pair uses the autosave written before the door input during an earlier successful replay, with only menu inputs. The replay will show where the autosave places the player.

Both replays of that autosave completed with the same source-verified release, a 1280×720 scene and menu inputs only. The reflection pass recorded in the enabled arm and was absent in the disabled arm. With reflections off, the bedroom was already in view at 90 seconds. With them on, the exterior was in view through 117 seconds and the bedroom was in view at 125 seconds. The sampled bedroom views used different camera angles. At 135 seconds the off run was on a close-up while the on run still showed the player from behind. The 15 Hz recordings cover roughly 103–155 seconds. This verified an indoor route and exercised the switch, but leaves the flicker and reflective-surface comparison open. The planned repeat starts recording at 55 seconds and runs to 215 seconds. These saved replays use copied warm caches and are excluded from the first-boot FPS comparisons.

The wider repeat completed in reverse order on the same release. The enabled arm recorded the 853×480 reflection pass and the disabled arm did not record it. Both reached the bedroom by the 140 s captures. A three-second thumbnail comparison of the two full recordings found closely matched views of the exterior around 120 s. The eight closest candidates were all outdoors. The sampled bedroom views still differ in pose and camera angle. This gives an outdoor match and no controlled comparison of an indoor reflective surface. The saved replays are visual checks with copied caches.

I repeated the thumbnail search starting at about 140 s in both replays. The nearest three-second bedroom candidates still face different parts of the room. The closest normalized gradient distance was 0.844 indoors versus 0.025 on the matched exterior shot, and inspecting the frames confirmed the camera mismatch. The current replay still cannot tell whether the pass changes indoor flicker.

Both later 245-second camera-sweep replays completed on the same release and copied autosave. The enabled arm again recorded the 853×480 reflection pass. Both reached a bedroom view, then the enabled arm spent most of its recording in the pause menu while the disabled arm remained in gameplay. The nearest three-second match had a gradient distance of 0.868 and paired gameplay with that menu. The closest sampled pair with both in the room still showed different camera angles. The sweep therefore supplies another incomplete visual comparison and the current default stays in place. These are warm saved-scene replays.

### Desktop play profile at 720p

The interactive session that produced the waterfront save reported 32,585 presents in 1,948.58 seconds of complete reporting intervals (16.72 FPS and 5,043 draws/frame). It includes menus and gameplay. The submission thread worked 53.46 ms/frame. The GPU queue was empty for 35.25 ms/frame, including 31.05 ms while that thread was working. This points to CPU submission work as a candidate in this session. The interactive timing uses the desktop caches and is separate from the clean first-boot baseline.

### CPU costs in submission preparation

Two isolated tests use the generic queue and range-merging code from each revision. They ran eight alternating pairs on one pinned Ryzen 7 9700X core. For the queue fixture each batch uses four logical queues round-robin and checks the full execution order. In the waiting case the first queue starts blocked, the other three run, then the fence opens. At a depth of 16, taking a ready front entry directly reduced median time per batch from 1,781 to 1,343 ns, and from 1,828 to 1,714 ns with the initial wait. At depth one with the initial wait both medians were 122 ns.

For two calls to merge 16 address ranges, collapsing overlaps in the existing vector took 83 ns against 110 ns with clustered addresses and 80 ns against 117 ns with more dispersed addresses. The clustered 64-range case was 420 ns against 419 ns. The fixture checks the union against an independent byte map, including empty and reversed ranges. These CPU timings measure isolated helpers. Neither test measures a game frame.

Run from a checkout that has both revisions. Each command compiles the corresponding helper from Git and runs both versions in alternating order.

```sh
python3 benchmarks/submission_cost.py 830dc191 b0a37d79 --workload queue
python3 benchmarks/submission_cost.py 830dc191 d408c01d --workload ranges
```

The ready-front change alone then completed a clean 1280×720 first boot. In 300 seconds it presented 2,574 frames (8.58 FPS), versus 3,298 (10.99 FPS) on the earlier control. P99 was 2.43 s against 1.74 s. The 70, 85, 100, 115 and 130 s captures on this attempt had a black or nearly black world; subtitles appeared in some of them. The reference showed outdoor scenery and characters during that period. Later captures in the changed build showed the car and credits. The microbenchmark gain did not translate into a demonstrated gameplay gain. The desktop preset stays on the original path while this opening is investigated. [Queue change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/15)

A second control and ready-front run gave 3,954 and 3,644 presents in 300 s (13.18 and 12.15 FPS), with P99 of 362 and 577 ms. Gaps over 100 ms took 154.08 and 168.34 s. The second ready-front run showed the building in the 70–100 s captures and the diner and street at 115–145 s. The second control had a black center at 70 s and the same washed-out frame at 85, 100 and 115 s. The first ready-front run's five dark samples did not recur on the second. Both ready-front runs were slower than their respective controls. The private captures show different scene progression between runs.

The range-merge change alone presented 3,644 frames in the first 300 s (12.15 FPS) with all five caches empty. The earlier control presented 3,298 (10.99 FPS). P99 was 570 ms versus 1,743 ms, but the worst gap was still 11.23 s versus 11.19 s. The range run showed the exterior at 85 s and the two characters in the car at 205 s; the reference had reached credits at 205 s. This is a positive first result with different scene progress. It needs repetition before treating the difference as a gameplay improvement. [Range merge change](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/16)

The range-merge repeat delivered 2,889 presents in 300 s (9.63 FPS). The second stock control gave 3,954 (13.18 FPS). P99 was 539 versus 362 ms, and >100 ms gaps took 187.92 versus 154.08 seconds. The earlier 12.15 versus 10.99 FPS result did not repeat. At 85 s a dark rectangular area covered most of the repeat's view. At 115 and 130 s a large stretched shape crossed the foreground. The first range trial had shown the diner at 100–115 s. These samples include different workloads and do not establish which change caused the bad frames. Three interrupted range repeats were excluded.

### Texture write-history query

The normal texture refresh asks whether any page was written since it last read the texture. The upload worker's first read needs only the asking number. With write history already available, this fixture compares building the page list and checking it with asking that question directly. It takes the two query functions from the supplied revision and checks their answers against independently generated write history. OS write-watch calls, locks, hashing, detiling and GPU uploads are outside this measurement.

Run this from the runtime checkout with the candidate revision available. The fixture runs natively with an optimizing Rust compiler and needs no game files or GPU.

```sh
python3 "$bench/texture_query.py" e6b99130 --pairs 7
```

| Range | Condition | Page list | Direct query |
|---|---|---:|---:|
| 1 page | All clean | 18 ns | 14 ns |
| 16 pages | All clean | 80 ns | 23 ns |
| 256 pages | All clean | 459 ns | 184 ns |
| 256 pages | Some writes newer than the last read | 310 ns | 45 ns |
| 1,024 pages | All clean | 1,178 ns | 640 ns |
| 1,024 pages | Some writes newer than the last read | 952 ns | 53 ns |

These are median times per query across seven alternating pairs. Each pair used 193 starting addresses. The direct query stops at the first newer write and skips the scan entirely on a first refresh. In a separate 32-minute saved session at 720p, the median reporting interval after the first two minutes attributed 9.5 ms/frame across all threads to the entire write-watch and guard step. That counter includes kernel and guard work and overlap between threads. It cannot be used as a prediction of FPS.

### Reserved VirtualQuery ranges

I tried adapting the reserved-range cache from [Avatar #377](https://github.com/avatarmanz/VIctory-7900XTX/pull/377) to the AMD runtime. Both runs started with five empty graphics caches, no story slot and the same verified 1280×720 release and vkd3d-proton GE `cae8353ed7959c4`. The only setting changed was `VICTORY_QUERY_HOLE_FRAMES`.

| First 300 seconds | Presents | Average FPS | P99 gap | Longest gap | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Off | 2,442 | 8.14 | 2,769 ms | 11.41 s | 202.97 s |
| 30 frames | 2,187 | 7.29 | 3,690 ms | 11.59 s | 209.50 s |

The enabled run showed the exterior clearly at 85–115 s. The off run was mostly dark during two of those captures and washed out at 115 s. Both later displayed faces in the car and showed the same tower at 295 s. The cuts and early visible work differed. The cache stays opt-in after this slower pair. An ordinary commit outside the runtime can also leave a reserved-range answer stale for the configured lifetime. This release comparison did not collect per-site query counts. The expiry and overlap-invalidation test passed on Windows MSVC under Wine. [Tested build](https://github.com/UwUCammie/VIctory-7900XTX/commit/87689ad3)

### Yielding a compile to other work

`competing_build.py` counts compiler processes and also recognizes parallel make/ninja invocations. For timing the game, run it with no arguments so every build counts. For guarding a compile, start that compile in its own session (Python's `subprocess.Popen(..., start_new_session=True)`) and pass its PID to `--exclude-session` while it runs. This excludes the compiler and build driver in that dedicated session. Two outside compiler processes plus a serial compiler of our own previously looked like three outside compilers and could cancel the serial job. Three outside compilers, or a parallel make/ninja invocation outside that session, still trigger a yield. GPU ownership is checked separately.

### Saved-game visual trials

A saved route can end with the Wine wrapper reporting zero even though the renderer logged an unhandled exception. Classify the exit before comparing captures or starting the next arm. The checker distinguishes a foreground interruption, an incomplete run, a host GPU failure and a renderer failure. A finished timeout still needs the requested scene, output size and interface plane checked. Saved routes use a copy of the player's save and do not contribute to cold first-boot FPS.

```sh
python benchmarks/saved_route.py "$run" --overlap "$attempt/foreground-overlap" --elapsed "$wall_seconds" --target 161
```

### Card fills with buffer copies handled on the CPU

On the same executable, the two stock runs used `VICTORY_CARD_STEPS=2`. Changing only that setting to `1` kept GPU fills and returned buffer copies to the CPU. Each measurement starts at the launcher with five empty caches, no story save, the same scripted inputs, a 1280×720 scene and the 3840×2160 interface plane. The first 300 seconds include loading and stalls.

| Setting | Presents | FPS | P99 gap | Time spent in gaps over 100 ms | Intervals reporting GPU buffer copies |
|---|---:|---:|---:|---:|---:|
| Stage 2, first control | 3,298 | 10.99 | 1.743 s | 177.0 s | 4 / 163 |
| Stage 2, second control | 3,954 | 13.18 | 0.362 s | 154.1 s | 3 / 181 |
| Stage 1 | 2,480 | 8.27 | 2.545 s | 190.6 s | 0 / 148 |

Stage 1 still recorded GPU fills in 117 of its 148 intervals. Its captures at 70, 85 and 100 seconds were black. The world was visible by 115 seconds, and the final captures showed a lit interior while both controls were still in the opening credits. The runs progressed through different scenes, so the FPS difference does not isolate the cost of a buffer copy. Eight interrupted attempts were excluded.

### Diner reflections at 720p

Two 150-second warm starts on the RX 7900 XT reached the diner with the same executable and input sequence. Each used a private copy of the same application and vkd3d caches, no story slots and `VICTORY_AMBIENT=0.8`. The only switch changed was `VICTORY_AMBIENT_REFLECT`, from 0 to 1. The enabled run recorded a reflection pass at 853×480 within the 1280×720 output. I matched the shots by camera angle and pose because the opening advanced at different times.

With the pass off, blue-white glare obscured both irises in the close-up. With it on, both irises were visible. In a second shot, mean luma in a 59×13 patch of the reflective floor went from 59 to 24 (0–255). In the same two frames the server's shirt read 170 and 171 and a ceiling light read 177 and 175. These are decoded video samples from comparable shots. They establish a visible change to these surfaces. Geometry flicker and cold-start frame time need their own checks. [AMD pull request](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/14)

I then timed two clean first boots of the reflection executable from process launch, with identical unskipped input, no story save and all five graphics caches empty. Both used the verified 3840×2160 UI plane and a 1280×720 host output. The enabled arm recorded the pass at 853×480. Both reached the same opening location at 85 s, but at 145 and 205 s the shots differed.

| Reflection limit | Presents in 300 s | FPS | P99 gap | Longest gap | Gaps over 1 s | Time in gaps over 100 ms |
|---|---:|---:|---:|---:|---:|---:|
| Off | 4,202 | 14.01 | 329 ms | 11.14 s | 30 | 146.99 s |
| On | 4,084 | 13.61 | 493 ms | 11.41 s | 31 | 150.90 s |

One pair measured a 0.39 FPS difference. The startup stalls and different scene progress make this insufficient to estimate the pass’s frame cost. The visual comparison above used matched shots.

### November 26 fork check

I kept the Linux/RADV tests on [linux-amd-best](https://github.com/jtrudeau1530/VIctory-7900XTX/tree/830dc191d749f6e9d30226a0a87dbb20607fcc40). One new [PortWatch](https://portwatch-vi.xyz/) lead, [VIctory-leonida](https://github.com/lepotane/VIctory-leonida/tree/c6c9da9f), reports 18.1 native average FPS in the world at 1080p on an RTX 4060 Ti under Windows. Its higher output figure uses NVIDIA Smooth Motion. Its shared-upload pool is worth measuring separately on RADV, but the host allocation patch needs a port to this branch. [Source change](https://github.com/lepotane/VIctory-leonida/commit/c6c9da9f)

[Kelvaroq](https://github.com/stellarr-studio/kelvaroq) moved organizations. Its translate-once result measures descriptor bookkeeping on an RTX 5080. I found no published first-story, cold-cache 720p RX 7900 XT average in the new scouting entries.

PortWatch also reports about 22 FPS in play for Belobug on Windows 11 with an RX 9070 XT and Ryzen 7 9800X3D. The entry names `main` and gives no tested commit, cache conditions or timing window. When I checked, `main` was at `4f62c2a5`; the default branch `a-publier` and `rx9070xt` were both at `cd8dfc06`. The latter includes a texture-upload ordering change worth testing for flicker on RADV. I kept the RX 7900 XT cold series on its existing base. [Tracker entry](https://github.com/4lwayz/portwatch-vi/blob/cd68b936/data/tracker.json) · [Main](https://github.com/Belobug/VIctory-Belobug-AMD/tree/4f62c2a5) · [Published build source](https://github.com/Belobug/VIctory-Belobug-AMD/tree/cd8dfc06) · [Upload change](https://github.com/Belobug/VIctory-Belobug-AMD/commit/5d6bd841)

Protonida's tracking request reports 20.4 FPS in the heavy city scene and up to 29.3 FPS in a lighter scene on an RTX 4050 laptop under Wine, using the 720p Series S profile with screen-space lighting. Those are scene measurements. I checked its 1M-descriptor-heap allocation change against the fork's existing alignment test. Running the unmodified helper and test with `rustc --test` on Linux reproduced a failure at offset 56, stride 56 with no raw twin (`8c0370bf`). The same test passed with the `linux-amd-best` helper at `830dc191`. I left this change out of the Radeon build pending a GPU readback on that descriptor path. [Tracking request](https://github.com/4lwayz/portwatch-vi/issues/207) · [Scene results](https://github.com/deynesdev/Protonida/blob/8c0370bf/README.md) · [Reproduction on the source commit](https://github.com/deynesdev/Protonida/commit/175ebc49bb5762061ceef4ff79a46599b76858fe#commitcomment-212014200)

### November 27 fork check

Victory Grimkaaah reports 13.9 FPS in the world with ray tracing, at 4K output on an RX 7900 XTX under Windows. Its shaders were already translated. The report credits making buffer copies during loading for reducing its first-world freeze from 5.2 to 3.8 seconds. Projeto Lucia reports 5–6 FPS in the world on a GTX 1650 SUPER with a warm-up step. The RX 7900 XT cold series stays on the Linux/RADV branch. [Grimkaaah submission](https://github.com/4lwayz/portwatch-vi/issues/241) · [Grimkaaah source](https://github.com/Grimkaaah/Victory-Grimkaaah/tree/7dbe7931) · [Projeto Lucia submission](https://github.com/4lwayz/portwatch-vi/issues/243)

PortWatch added VIctory-NVIDIA. Its README reports 26–30 rendered FPS in opening rooms at 1440p with DLSS Quality on an RTX 5070 under Windows 11. The project also uses an estimate for lighting and reflections by default. That result covers a different hardware, rendering and measurement setup from the 300 s RX 7900 XT cold run. [PortWatch](https://portwatch-vi.xyz/) · [VIctory-NVIDIA measurement](https://github.com/trustno1-coder/VIctory-NVIDIA/blob/d12eb1b23da4cad2f551a3dd49e82a87e564122a/README.md#where-it-stands)

The fork publishes a hypothesis that an invalid indirect record can exhaust its list's budget and make the later draws run empty. Wine already has the same `VICTORY_INDIRECT_REST` switch. All 195 interval summaries in the completed cold reference and 101 in the interrupted saved-route attempts reported 0.00 budget-refused indirect records per frame. The saved attempts have yet to finish the intended camera route. A paired gameplay check needs an occurrence of the reported flicker on that route. [Foxhound findings](https://github.com/trustno1-coder/VIctory-NVIDIA/blob/d12eb1b23da4cad2f551a3dd49e82a87e564122a/docs/findings.md#what-is-next)

The shared-buffer pool from Avatar #433 targets allocations made for off-element buffer views and command-list uploads. In the reverse-order 720p runs above, the combined and stock builds peaked at 45 and 70 retained exact views. Their last cumulative mapping counters showed 21,400 and 19,800 waits and 15.6 and 18.0 seconds across threads. Those totals include allocations from all callers and can overlap. The AMD adaptation has both settings opt-in. The first hardware fixture uses the upload pool alone and exercises list-reset ownership. [Upstream discussion](https://github.com/avatarmanz/VIctory-7900XTX/pull/433#issuecomment-7211359080) · [AMD candidate](https://github.com/UwUCammie/VIctory-7900XTX/commit/acfb2357)

### Cold follow-up with the 500 ms compute scheduler

This run used the revised [Avatar #166](https://github.com/avatarmanz/VIctory-7900XTX/pull/166) scheduler with the [720p interface and present trace overlay](https://github.com/UwUCammie/VIctory-7900XTX/commit/a995ba9c). The loaded driver was vkd3d-proton `71cae091b06571e`. The log confirmed a 500 ms graphics wait. The control used compute wait off.

The clean run accepted **2,610 presents in the first 300 seconds (8.70 FPS)**, with a 627 ms P99 and a 2.51 s longest gap. It spent 210.75 seconds in gaps over 100 ms. Eight overlapping control attempts were excluded. The first enabled attempt yielded to another GPU client and was excluded. The enabled runtime logged both 500 ms budgets before it yielded.

The control accepted 566 presents between 30 and 220 seconds (2.98 FPS). Across three subdivisions of that interval, median reported preparation was 111–150 ms/frame, with copies accounting for 60–92 ms/frame. Those are medians of renderer samples. The full-window FPS is from the accepted-present trace. A private close-up around 190 seconds showed eyes and teeth with the facial surface missing, reproducing the earlier observation on a clean run. The same car close-up showed facial skin at about 192 seconds with compute wait enabled. The enabled capture predates that attempt’s build overlap by about 24 seconds. Both launches used the same executable, driver files and inputs. A complete enabled timing is pending. [Upstream discussion](https://github.com/avatarmanz/VIctory-7900XTX/pull/166#issuecomment-7211416953)

### Out-of-order graphics wait budgets

The revised compute scheduler keeps a newer compute frame when a recorder arrives late. Its graphics and screen wait path still reset the budget whenever a recorder presents a different frame number. An older recorder could therefore replace the newer budget, and the next recorder on the newer frame could take a fresh allowance. The [follow-up](https://github.com/UwUCammie/VIctory-7900XTX/commit/2fb4f80c) carries over [AMD #52](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/52) on the exact revised scheduler base.

The native check extracts the budget function and its regression. It verifies older, current and newer frames in both shared and non-shared modes.

```sh
python -B benchmarks/compute_reserve_fixture.py PATH_TO_BUDGET_CHECKOUT --graphics-budget
```

### Measuring compute waits against the frame deadline

The revised scheduler calculates a 500 ms deadline when the first compute wait starts. The caller previously converted that deadline to a duration before taking the priority queue lock, then started a second timer after it got through the lock. That could add lock and scheduling time to the allowed wait. The [follow-up](https://github.com/UwUCammie/VIctory-7900XTX/commit/ab9c444a) carries the absolute deadline into the wait loop.

The native check passed on the extracted deadline code. It verifies that a delayed caller gets the same deadline, that a wait begun late has only the remainder available, and that later and older frame numbers follow the existing frame ordering.

```sh
python -B benchmarks/compute_reserve_fixture.py PATH_TO_DEADLINE_CHECKOUT --compute-deadline
```

The [combined 720p build](https://github.com/UwUCammie/VIctory-7900XTX/commit/ea99e42a) adds both budget fixes to the revised scheduler control. The compare step checks different runtime digests, the same three driver DLLs, the same inputs and flags, and both logged 500 ms wait settings. The first 300 seconds are timed from two separate cold boots. The output check and matched car close-up are part of the comparison.

### Keeping one general pipeline worker available for compute

The default revised scheduler lets a screen pass use the last general worker. The [strict reserve experiment](https://github.com/UwUCammie/VIctory-7900XTX/commit/2c7a51f0) leaves screen work to its dedicated workers when only the reserved general worker is available. In both arms, compute and graphics waits stay at 500 ms. The only switch changes from `VICTORY_COMPUTE_STRICT_RESERVE=0` to `1`.

The [native fixture](compute_reserve_fixture.py) extracts the queue implementation and seven of its tests. It supplies ready-to-use dummy pipeline records and runs without the Windows SDK or a game. All seven passed, including the check for urgent compute with a screen job simultaneously queued.

```sh
python -B benchmarks/compute_reserve_fixture.py PATH_TO_RESERVE_CHECKOUT
python -B benchmarks/cold_boot.py RUN_DIR LAUNCH_JSON --stop 300 \
  --expect-output 1280x720 --expect-interface 3840x2160 --expect-vkd3d 71cae091 \
  --expect-graphics-wait-ms 500 --expect-compute-wait-ms 500 --expect-compute-reserve 1
```

Use `--expect-compute-reserve 0` for the control. The scorer reads the startup worker configuration and records whether a screen compile took the reserved worker. The cold gameplay results are pending.

### Late card-step fills on the AMD branch

[Avatar #434](https://github.com/avatarmanz/VIctory-7900XTX/pull/434) traced stretched geometry to constant-buffer fills that read too early. [AMD #56](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/56) ports the check with `VICTORY_CARD_STEPS_LEARN=1` opt-in. The Windows MSVC build passed nine Wine tests, including a fixture with changed and unchanged pages for both fill paths. The separate flight test passed with learning off and on on RX 7900 XT, RADV 26.3.1 and GE vkd3d-proton `cae8353ed7959c4`. [Hardware result](https://github.com/avatarmanz/VIctory-7900XTX/pull/434#issuecomment-7211813455)

The [720p integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/a9624438) is for a saved indoor camera replay. Both launches use the same copied save and caches, executable, stock GE driver DLLs, relay stage 2 and card steps 2. The only switch is `VICTORY_CARD_STEPS_LEARN`. Check the reported switch, the number of pages learned and submissions that waited, and comparable camera angles in the private recordings. The saved-route observation does not enter the cold-start FPS series.

The compilation guard interrupted the first test build after roughly 35 seconds. Marking the source files fresh once before the guarded operation let Cargo keep its completed crates on retry. The retry rebuilt the remaining GPU crate and finished in 30.26 seconds. Source checksums from the final PDB verified the code used for the tests.

### Cold upload-pool comparison

The [720p integration build](https://github.com/UwUCammie/VIctory-7900XTX/commit/47d8e27a) adds [AMD #55](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/55) to the combined CPU branch. Use the same executable, driver DLLs, Series X profile and input sequence in both launches, with five empty graphics caches and no story slots for each. Set `VICTORY_CARD_STEPS=2`, `VICTORY_VIEW_POOL=0` and `VICTORY_VIEW_POOL_MB=256` in both. Change `VICTORY_UPLOAD_POOL` from 0 to 1.

```sh
python -B benchmarks/cold_boot.py RUN_DIR LAUNCH_JSON --stop 300 \
  --expect-output 1280x720 --expect-interface 3840x2160 \
  --expect-vkd3d cae8353e --expect-upload-pool 1
```

Use `--expect-upload-pool 0` for the control. The scorer checks which setting the shared upload path used and reports the latest cumulative pool and mapping counters logged before the cutoff, with their sample times. Mapping waits include all callers and may overlap. Both arms are timed from launch. Gameplay results are pending.

### Cold title-buffer allocation prefetch

The [experimental integration](https://github.com/UwUCammie/VIctory-7900XTX/commit/08298c2a) queues exact 64 KiB-aligned allocation sizes while title buffers are declared. A worker can hold up to 64 MiB of fresh shared buffers, with 128 pending requests and a 4 MiB maximum per allocation. A first-use request can take a prepared allocation of the same size. The existing shadow and memory placement decisions still run at first use. Grimkaaah’s different copy-ahead implementation reported a shorter first-world freeze on Windows. [Source measurements](https://github.com/Grimkaaah/Victory-Grimkaaah/blob/7dbe7931/CHANGES.md)

For the cold pair, set `VICTORY_BUFFER_PREFETCH=0` and then `1` on the same executable. Use the same stock GE driver files, Series X profile and input sequence. Start each launch with five empty graphics caches and no story slots.

```sh
python -B benchmarks/cold_boot.py RUN_DIR LAUNCH_JSON --stop 300 \
  --expect-output 1280x720 --expect-interface 3840x2160 \
  --expect-vkd3d cae8353e --expect-buffer-prefetch 1
```

Use `--expect-buffer-prefetch 0` to check the control. The report includes the last queued, prepared and used counts before 300 seconds. The test measures whether moving allocation work earlier helps the entire launch. Gameplay timing is pending.

### Verify pipeline-library persistence without the game

A separate [vkd3d-proton library fix](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/4) addresses repeat launches. On this branch the host refused its empty library, so it could not save pipeline entries or the list of pipelines to start early next time. The two independent control launches both reported the refusal. A small probe exercises the driver's empty-library calls and serialization without a game or shader compiler. Build `empty_pipeline_library.cpp` in a Windows developer prompt:

```bat
cl /EHsc empty_pipeline_library.cpp d3d12.lib
```

Run the resulting executable against the same D3D12 implementation as the game. Here the non-null pointer with zero length gave `80070057`, the null pointer gave `00000000`, and the resulting 56-byte serialized library reopened successfully. First-boot trials always start with an empty pipeline directory.

With the fix in the runtime, two first story launches wrote pipeline libraries from empty directories. At 1 KiB the library reached 426,680 bytes and the early list had 2,348 entries. The launch averaged 13.27 FPS, with a 396 ms p99 and an 11.27 s hold. The opening cinematic continued through the movement window. At 2 KiB the library reached 456,248 bytes with 2,269 early entries. The launch averaged 13.75 FPS (4,125 frames) and the verified cell movement averaged 25.59 FPS (1,919 frames). P99 was 279 ms and the longest hold was 11.12 s. The face pipeline was ready before its first bind in both runs.

A separate process started with a copy of only the application pipeline directory from the 1 KiB run. The saved library reopened at its original size. By its second save the runtime reported 2,228 library loads and three new builds. This 45-second diagnostic is excluded from every first-boot FPS figure. The desktop now uses the library fix with the 1 KiB preset. A cold control using the same executable without small-compute scheduling still showed the eyes and teeth without facial skin, so persistence alone does not fix the first launch.

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

## Shadow buffer comparison under Wine

[Avatar PR 376](https://github.com/avatarmanz/VIctory-7900XTX/pull/376) changes how `shadow::find_pieces` checks a 64 KiB piece against its snapshot. This fixture compares the original byte-slice inequality with the actual `safecopy::differ` from the runtime checkout. It checks agreement on unaligned buffers and lengths around the vector boundaries, then rotates over 128 generated pieces at a three-byte offset. The two comparison methods run in alternating order on the same buffers. A warmup pair is discarded.

Optimized x86-64 MSVC executable under Wine 11.22, Ryzen 7 9700X, eight measured pairs. The executable imports `memcmp` from `VCRUNTIME140.dll`. Values are median nanoseconds per 64 KiB piece. The AVX2 check was quicker in all eight pairs for each case.

| Contents | Slice comparison | AVX2 comparison |
|---|---:|---:|
| Equal | 1,599.5 | 990 |
| First byte differs | 10 | 8 |
| Middle byte differs | 824.5 | 565 |
| Last byte differs | 1,614 | 1,013.5 |

From a configured Windows MSVC Rust environment:

```sh
python benchmarks/shadow_compare.py prepare PATH_TO_RUNTIME shadow_compare.rs
rustc --edition=2024 -O shadow_compare.rs -o shadow_compare.exe
./shadow_compare.exe > pairs.txt
python benchmarks/shadow_compare.py report pairs.txt
```

For a Wine comparison, cross-compile the same generated file with `--target x86_64-pc-windows-msvc` and run it with Wine. No GPU or game data is used. This isolates the byte comparison. The descriptor reference-count change and whole-frame time require separate measurements.

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

## Reusing the relay readback snapshot

A five-second profile counted 140 of 3,353 samples inside the runtime image in `card_merge_relay`. The [AMD change](https://github.com/UwUCammie/VIctory-7900XTX/commit/e0f47673) brings over the [empty-exclusion fast path](https://github.com/fxceless/victory-fork/pull/1427), keeps the AMD sent-range index, and reuses the original title-byte snapshot across the fetched pieces in a relay batch.

Two Windows MSVC tests passed under Wine on an RX 7900 XT with RADV 26.3.1 and GE vkd3d-proton `cae8353ed7959c4`. The generated landing test checked 80 pairs with and without exclusions. It compared the bytes written to title memory and the CPU reference bytes with the parallel landing path.

The [snapshot fixture](relay_snapshot.rs) uses a counting allocator on generated 4, 8, 12 and 16 KiB inputs. Over 11 alternating pairs on one Ryzen 7 9700X core, allocation and reallocation calls per 6,400 snapshots fell from 6,400 to 300 in every pair. The instrumented medians were 69.8 and 60.0 ns per snapshot. Nine pairs favored reuse. This isolates the snapshot copy and allocator work. Gameplay timing is pending.

```sh
rustc --edition=2024 -O benchmarks/relay_snapshot.rs -o /tmp/relay-snapshot
/tmp/relay-snapshot
```

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

## Window placement on the RX 7900 XT

One release compared direct GPU upload windows, staged windows and shared memory. The early run with direct upload skipped the intro. The others played it. Only the last complete intervals (166–182 s) in each run showed the first room in all three.

| Backing | Presents | Seconds | FPS | Draws/frame |
| --- | ---: | ---: | ---: | ---: |
| Direct GPU upload, 512 MiB cap | 129 | 14.79 | 8.72 | 4,799 |
| Staged, 512 MiB cap | 85 | 14.44 | 5.89 | 4,964 |
| Shared memory | 80 | 15.16 | 5.28 | 4,965 |

In the reverse-order repeat with ordinary taps, shared memory gave 482 presents in 54.26 s (8.88 FPS, 4,875 draws/frame) from 170–225 s. The center of the window changed 9.26 and 8.86 times per second in two five-second samples. The direct-upload repeat lost the GPU at 38.2 s, well before gameplay. The launcher returned zero. With shared memory spanning 5.28–8.88 FPS across visits, these measurements do not establish a placement advantage. The reporters now reject sessions containing a terminal GPU error even if they logged accepted presents earlier. The separate accounting test used a 4 MiB cap and passed on both GPU backings. [Budget regression and physical tests](https://github.com/fxceless/victory-fork/pull/1250)

## Opening dialogue visual check

The fast room route skips the diner. A view of the player's back and an advancing frame counter can confirm gameplay while missing two defects visible from the front. To check this build on the RX 7900 XT, leave the dialogue running, compare the server's face, neck and forearms during the order, and inspect several frames of the seated character speaking. Align runs by the same shot and line of dialogue. A single open-mouth pose cannot show whether the lips, teeth and jaw move together.

On the gather build with the copy-back worker set to either 0 or 2, the server's face could appear black while her forearms and clothing drew. In other shots the seated character had visible skin but the upper lip stretched toward the nose. The same deformation is visible in an earlier control run. Rechecking placed textures after streaming writes made 2,985 previously uploaded slots due again in one run. The server's face still failed the visual check. An integration of the fair queue, the latest half-view change and ordered-pixel support also reproduced both defects.

The hardware half-view test preserved all 65,536 patterns through integer views. The float control preserved one. Ten of 280 character-texture pixel programs failed to emit on the older build. All 280 emitted on the integration, and all ten previously failing programs created a host pipeline on the GPU. None of those ten appeared in the recorded first binds of the affected opening shots. [Facial-animation results](https://github.com/fxceless/victory-fork/pull/927#issuecomment-7180848831) · [Texture scheduling results](https://github.com/fxceless/victory-fork/pull/1246#issuecomment-7180852203) · [Ordered-pixel results](https://github.com/fxceless/victory-fork/pull/215#issuecomment-7180873951)

Two runs on the same RX 7900 XT build compared fixed texture-copy budgets of 4 GiB and 8 GiB. In both, the server's face was blotchy red during the same reply to the water order, and her forearms had their usual skin color. The wall behind the seated character was visible in the 8 GiB run and dark in the 4 GiB run. In both, her upper lip pulled toward her nose across successive frames of the next line. The 4 GiB run had 24,862 texture slots due during the exchange, including 5,646 fully mapped entries whose textures had never received a host copy. This establishes a backlog. Identifying the resources sampled by the face still requires a draw-level check. Each budget was tested once.

## First room with 32-bit typed views and legacy multiply-add

I replayed the diner and the first room on the RX 7900 XT, with bake-source uploads enabled throughout. The parent is the bake-source build at `3d3a055`. The second build also includes the 32-bit buffer-view change from #684 and the legacy multiply-add change from #1026. Each row is one launch. The window is 165–215 s from the first log timestamp. At both ends the room and character were visible.

| Build and vkd3d setting | Accepted presents | Seconds | FPS | Draws/frame | Visible changes/s in two samples |
| --- | ---: | ---: | ---: | ---: | --- |
| Parent | 579 | 49.03 | 11.81 | 4,826 | 11.68, 11.68 |
| Both shader changes | 597 | 49.15 | 12.15 | 4,800 | 11.88, 12.48 |
| Both changes, FORCE_NOCONTRACT_MATH across all shaders | 532 | 49.57 | 10.73 | 4,839 | 11.68, 9.87 |

The second build ran first. The third run used a fresh vkd3d pipeline cache and a build overlapped its last part. These samples establish achieved frame rates on this visit. They do not isolate a speedup or the cost of the math setting. Lucia's clothing also differed in the diner. During the same dialogue the lip still stretched toward her nose in all three runs. The server's face was visible in the second and third runs; part of the parent's sequence still showed a red face.

A separate, game-free hardware test of legacy multiply-add returned zero on the fused-rounding case. Decorating only the SPIR-V Fma with NoContraction, or applying vkd3d-proton 3.1's FORCE_NOCONTRACT_MATH quirk with no shader override, made all four hardware cases pass. Neither the corrected synthetic result nor the diner result establishes the cause of the lip deformation. [Benchmark source](https://github.com/UwUCammie/victory-amd/tree/079d840) · [Hardware test and reproduction](https://github.com/fxceless/victory-fork/pull/1026#issuecomment-7187623405)

## Deferring buffer copy-back on the RX 7900 XT

With the 64 MiB GPU-written fixture from [the lazy copy-back PR](https://github.com/fxceless/victory-fork/pull/1178), the eager path took 37.606 ms per iteration with an idle CPU reader. Deferring copies took 1.296 ms and removed all 64 MiB of readback and upload per iteration. When the CPU touched 20 of 1,024 pages, the times were 37.257 and 2.867 ms. The deferred path transferred 1.25 MiB each way and recorded 20 demand faults per iteration. These timings cover the fixture on the RX 7900 XT.

The first gameplay replay on the contributor's original branch stopped with a copy-back thread panic. The [shared-buffer fix](https://github.com/Vladimir-Human/victory-fork/pull/2) covers both the panic and an independent stale-byte case in the parallel scan. With the [Wine test adjustment](https://github.com/Vladimir-Human/victory-fork/pull/1), all 16 lazy copy-back checks passed on this hardware in 0.40 s.

I then used one release binary with a 24 ms pipeline wait, the same timed inputs and a separate copy of the save data for each launch. With eager copies the first room was visible at 98, 118 and 131 s. Complete intervals between 98 and 131 s contained 249 presents in 32.25 s (7.72 FPS, 4,869 draws/frame). Both five-second window samples changed 7.65 times/s. With lazy copies, the process stopped on an unhandled write at 39.8 s, before the room. The last counters recorded 1,312 pages armed, 10,525 hits, 38 read faults, 185 write faults and 89 explicit flushes. Gamescope returned zero. There is no paired gameplay speedup from this run. [Exact replay source](https://github.com/UwUCammie/victory-amd/tree/abd6e69)

## CGBJ's public Windows release on the RX 7900 XT

PortWatch's [November 26 pin](https://github.com/4lwayz/portwatch-vi/blob/9a8fa4a0a/data/pinned.json) reports 25 FPS in gameplay and 30 FPS in cutscenes. Its [55-second clip](https://v.redd.it/137k5pow5w3i1) shows part of the plane cutscene and the boat mission. The on-screen counter reads 23 FPS at 50 and 53 seconds during the boat sequence. The pin gives no commit or frame-time log for the recording.

I built codec_d's [public release commit f4b48ad](https://github.com/DoubleGhosty/cool_fox/commit/f4b48ad766ddbec1a1867022cd42f7645b0dd55e) from a fork. The original GitHub repository returned 404 on November 26. I used the 19 renderer settings and Series S profile in its Windows launcher, the RX 7900 XT with RADV 26.3.1, Wine 11.22 with the tree-index wineserver, and vkd3d-proton GE build `cae8353e`. Both 190-second runs started with a copy of the same save. I used INFO logging and timed controller input to reach the first room. The [developer's journal](https://github.com/DoubleGhosty/cool_fox/blob/f4b48ad766ddbec1a1867022cd42f7645b0dd55e/docs/bug-journal.md) describes RTX 5090 testing.

- The unmodified release used fresh runtime and vkd3d caches. The first room was visible at 145, 160, 172 and 183 seconds. The HUD's periodic rates there were 3.6–3.7 FPS. Five-second samples of the window's center at 145 and 174 seconds changed 3.42 and 3.62 times/s.
- The repeat reused those caches. I applied the [successful-present check](https://github.com/avatarmanz/VIctory-7900XTX/commit/8699d96a2371ce4c557c256df1bc1d0cf057750a) and the [one-line interval counter](https://github.com/UwUCammie/VIctory-7900XTX/commit/378740b0619443e974c6a6628ce158d112370677). Complete intervals between 145 and 183 seconds gave 135 accepted presents in 37.16 s, or **3.63 FPS**, at 4,580 draws/frame. Both window samples changed 3.62 times/s. A surface to the right of the window rendered bright purple on both runs.

These runs measure the first room on Radeon under Wine. The machine, scene and unidentified build in the PortWatch footage differ, so the result does not establish a rate for the boat mission or for NVIDIA.

## The community Linux/RADV branch in the first room

The [RX 7900 XT setup in AvatarManz issue #111](https://github.com/avatarmanz/VIctory-7900XTX/issues/111#issuecomment-7187499094) identified a second candidate. I built its [3241322 revision](https://github.com/jtrudeau1530/VIctory-7900XTX/commit/3241322d96f217167d70af0608f192ae5cae9a87) in release mode with the posted switches, Series X and the tree-index Wine server. I used the existing successful-present counter and enabled scripted input in the release build so the same route would work headlessly. The initial run without the input hook spent part of its time at account selection and is excluded. [Exact instrumented source](https://github.com/UwUCammie/VIctory-7900XTX/tree/9d6b882)

With the published renderer settings, complete first-room intervals between 145 and 183 seconds gave 588 accepted presents in 37.07 s (15.86 FPS, 4,839 draws/frame). Five-second window samples at 145 and 174 s changed 15.91 and 16.11 times/s. At 50 and 72 s in the diner the seated character’s face and neck were missing while the hair and teeth drew. The room character also had a gap at the neckline.

With only `VICTORY_FETCH_CHECK=1` added to the same renderer settings, the same window gave 596 presents in 37.07 s (16.08 FPS, 4,861 draws/frame). Window samples changed 15.50 and 16.11 times/s. The check was active: across 23 reporting intervals between 55 and 80 s, the renderer checked about 896–1,706 fetched pieces per frame and recorded up to 11.46 mismatches/frame. In the diner both the server and seated character still showed eyes and teeth through absent skin. This differs from the [face result on an earlier revision](https://github.com/avatarmanz/VIctory-7900XTX/issues/138). The two timed launches used the same binary, copied starting save, initial runtime cache and initial vkd3d cache. The 0.22 FPS difference is one pair of runs.

I also tried the [earlier stage-one workaround](https://github.com/avatarmanz/VIctory-7900XTX/issues/13) by setting `VICTORY_RELAY=1 VICTORY_CARD_STEPS=0` on the published settings. It gave 446 accepted presents in 36.82 s (12.11 FPS, 4,851 draws/frame). Both window samples changed 11.88 times/s. The missing skin was visible on both characters during the water order. Each of the three configurations completed its 190-second run.

## Compute pipeline waits and Radeon buffer sizes

I built the [November 26 Linux branch](https://github.com/jtrudeau1530/VIctory-7900XTX/commit/830dc191d749f6e9d30226a0a87dbb20607fcc40) and replayed the diner and first room on an RX 7900 XT with a Ryzen 7 9700X, RADV 26.3.1, tree-index Wine 11.22 and vkd3d-proton GE build `cae8353e`. Each launch started with a separate copy of the same profile, story slot, runtime cache and vkd3d cache. The table counts complete successful-present intervals between 145 and 183 seconds. The last column counts changes in a 256×144 window crop during two five-second samples. These are Series X runs with the same timed input.

| Texture worker | Compute wait | GPU buffer minimum / budget | Presents / seconds | FPS | Draws/frame | Visible changes/s |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Off | Original renderer | 4 MiB / 2 GiB | 588 / 37.05 | 15.87 | 4,830 | 15.69, 16.11 |
| On | Original renderer | 4 MiB / 2 GiB | 582 / 37.34 | 15.59 | 4,788 | 15.70, 15.91 |
| On | On | 256 KiB / 4 GiB | 759 / 36.85 | 20.60 | 4,817 | 20.13, 20.74 |

Both original controls showed missing skin on the server and seated character. With Beqren’s bounded compute wait, both had visible faces and necks during the order on two separate launches, one with the texture worker off and one with it on. I then switched only the compute wait off in the **same executable** used for the worker-off replay. The missing faces returned. The profile and story slot were identical in these comparisons. The 20.60 FPS row also changes the buffer sizes, so it measures the combination. The texture worker by itself showed no first-room gain in the original pair.

The shell profile contains the exact renderer settings for the 20.60 FPS row and preserves environment overrides. The comparison sources include the same input hook and accepted-present counter. [Shell profile](radv_first_room.env) · [Original controls](https://github.com/UwUCammie/VIctory-7900XTX/tree/9eb196c7a2bc9256889f600c85f30cbf562aeffd) · [Compute-wait replay](https://github.com/UwUCammie/VIctory-7900XTX/tree/80685279a4a120d3198b9688d9f5b1c6aaf75d99) · [Linux branch PR](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/2)

Use `python -I benchmarks/first_room.py run.log --start 145 --stop 183 --costs` to check where time went in an existing run. It weights each interval by its successful presents and gives the number of frames that actually reported each cost. The timings overlap. On the 20.60 FPS Series X run, submission preparation averaged 46.28 ms/frame, the GPU queue was empty for 16.07 ms/frame, and merging fetched data took 13.09 ms/frame. Waits on title-memory reads averaged 5.75 ms/frame. The original worker-on run reported 60.76, 18.72, 11.71 and 12.69 ms/frame respectively. GPU waits attributed to the in-flight list limit and to overlapping shader writes averaged 0.00 ms/frame in both runs at the renderer’s reporting precision. This distinguishes the first room from the [boat measurement for larger in-flight limits](https://github.com/fxceless/victory-fork/commit/06702fe8).

I also checked the water-order line in the older recording that showed the stretched upper lip. On the current compute-wait build the facial skin stays visible, but the lips barely part in the four-samples-per-second recording. Facial animation remains open. A Series S run reached the room and walked away from the window. Another game started on the same GPU before the measurement window, so I excluded that run from the performance comparison.

### Matching the first-room camera

A 4K repeat reached the room but walked across it during the timed window. The raw constant-buffer translation run was still in dialogue at 172 s and at the window by 183 s. With placed constants the image stayed black despite successful presents. A second local game session overlapped all three runs. I excluded all three from the first-room comparison. The 1080p trial overlapped that session at startup and got an 8,134 MiB local GPU budget (the earlier 20.60 FPS run got 18,646 MiB). After the other game closed, the 1080p window scene at 125–149 s gave 388 presents in 22.57 s, 17.19 FPS and 4,982 draws/frame. The scene and startup budget both matter when comparing the result. [Black-output report](https://github.com/avatarmanz/VIctory-7900XTX/issues/163#issuecomment-7190646388)

For subsequent standing runs I sample a private reference view of the window and character at five-second intervals. Both the reference and candidate are averaged down to 32×20 RGB. In the earlier stills the matched room had mean absolute differences of 0–8 on a 0–255 scale. The closest frame in the walk-away repeat scored 26.6. The threshold for the next runs is 12. Choose the first 35 seconds of uninterrupted matches, inspect the stills and check visible motion independently. The script needs Pillow and keeps all images local.

```sh
python -I benchmarks/scene_window.py "$reference" "$run/cap" --threshold 12
```

The returned start and stop times work with `first_room.py`. Missing captures more than six seconds apart break the match. For a benchmark in a dedicated Linux user service, `yield_gpu.py --unit BENCH.service /path/to/foreground-busy` checks once a second and sends TERM to the benchmark's gamescope timeout when the foreground check exits zero. Pass `GOAL30_YIELD_MARKER` through to `timeout` as the absolute path to the attempt's `foreground-overlap`. The guard records it before sending TERM so an interrupted attempt can retry even if the launcher sees the process exit before its next check. The check here includes the desktop launcher's advisory lock because Wine sometimes calls a live game process `main`.

The guarded launcher uses `guard_quiet.sh` after polling both resources. A parallel CPU build starts a five-second quiet period, and GPU activity starts a separate 45-second period. The launcher still yields immediately on either active resource and excludes the attempt from full scoring. A CPU build never extends the GPU's recovery period.

The 1280×720 output test used the same display-patch executable as the 1080p run. It began with a 19,319 MiB local GPU budget. The standing character and window were visible at 115, 125, 142 and 149 s. From 115–149 s the complete intervals added up to **784 successful presents in 32.70 s (23.98 FPS)** at 4,883 draws/frame. The two independent motion samples measured 23.75 and 24.56 changes/s. Submission preparation averaged 40.25 ms/frame. The GPU queue was empty for 17.52 ms/frame. The setting changes the title's output to 1280×720; the original desktop run used 3840×2160. The startup budgets differ from the earlier 1080p measurement.

On separate Series X dialogue runs the original compute-wait build kept the seated character's lips almost closed. With the renderer and shader changes from AvatarManz #114 the jaw moved, but the upper lip pulled upward and left a large opening during the same turn toward the server. Both runs had facial skin and started with over 19 GiB of local GPU budget. [Paired dialogue result and setup](https://github.com/avatarmanz/VIctory-7900XTX/pull/114#issuecomment-7190790065)

### Saved waterfront with in-place indirect arguments

To check the private screenshots from a route, add `--sample-seconds 125 135 145 155` to `benchmarks/saved_route.py`. Each entry gives the fraction of the center half (in both dimensions) with every RGB channel at 6 or below. A missing capture produces `null`. Review the images themselves to distinguish a black world with a HUD from a fade during loading.

On the RX 7900 XT with RADV 26.3.1, Wine 11.22 and vkd3d-proton GE build `cae8353e`, the ordering-off run completed a 161 s saved-game route with `VICTORY_PORT_CONSTANTS=1`. The in-place path logged 86 samples with indirect draws and peaked at 5,536 executions per frame. Zero were ordered by the patch, as expected with `VICTORY_PORT_CONSTANTS_ORDER=0`. The HUD appeared over a black world. At 125, 135, 145 and 155 s, every pixel in the center half of the captured window had all three channels at 0 or 1 on the 0–255 scale.

An interrupted run with ordering enabled also showed a black world. A separate launch with ordering enabled exited at startup with a renderer breakpoint before any affected indirect draws were logged. These are observations on disposable copies of the same save. The setting for importing buffers in place was on in both runs. The port-off control completed with the same binary, starting save snapshot, cache inputs, camera inputs and 161 s timeout. At 125, 135, 145 and 155 s, the character and waterfront were visible. No center pixel at those times met the near-black threshold, against 100% with constants in place and ordering off. The stock control had zero in-place indirect draws. The order switch was at its default for that control and only applies to in-place draws. Both completed launches yielded a HUD. These results cover this saved route with the journal disabled. [AMD ordering patch](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/18)

### Write-watch page-part updates

The current AMD renderer records a generation for each written 4 KiB part of a 64 KiB page while holding the write journal. I tried visiting only the marked parts. The extracted native loops agreed for all 65,536 masks. Across 12 alternating timing pairs per case, portable x86-64 took 63%, 57% and 34% less time for 1, 2 and 4 marked parts. It took 11%, 65% and 84% more time for 8, 12 and 15. The x86-64-v3 build showed the same crossover. These are timings for the update loop with generated masks, without the journal or B-tree lock. The trial stayed off the gameplay build. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/cea72a5b)

```sh
python -I benchmarks/watch_part_bits.py PATH_TO_EXPERIMENT_CHECKOUT --base 830dc191
```

### Comparing compute frame budgets on the AMD renderer

The AMD renderer's compute wait has two limits. The pipeline age limit stays at ten seconds. The frame limit starts with the first compute wait in each frame. Runs with `VICTORY_COMPUTE_FRAME_WAIT_MS=500` and `10000` use the same executable, driver files, input, 1280×720 scene, and 500 ms graphics budget. Each run starts a new story with five empty cache directories. The 300-second window includes the time to the first present and every subsequent hold in that window.

For the 500 ms run, check the actual startup announcements along with the present trace. Use `10000` for the second run's last argument.

```sh
python -B benchmarks/cold_boot.py "$run" "$launch" --start 0 --stop 300 \
  --expect-output 1280x720 --expect-interface 3840x2160 --expect-vkd3d 71cae091 \
  --expect-graphics-wait-ms 500 --expect-compute-wait-ms 10000 --expect-compute-frame-ms 500
```

The first 500 ms attempt reached the car dialogue on the RX 7900 XT. The passenger's face and skin were visible in a local capture saved 161.55 seconds after launch. The run yielded to another build 17.90 seconds later, so it has no 300-second result. This observation covers one shot. Matched character and lighting checks still require the complete pair.

### Selecting write-watch requests left after the first pass

The write-watch pass skips a range when one earlier request covers it. A tree can track those covering ranges without scanning the entire request list repeatedly. The generated fixture compares the exact request sequence, including overlapping ranges that are only covered by a union. Across 400 generated sequences, the first tree implementation selected the same requests as the scan. With 4,096 shuffled disjoint inputs it took 6.82 ms versus 0.47 ms in eight alternating timing pairs, while 16 such inputs took 77 ns versus 247 ns. Dense nested inputs were slower across the tested sizes. The timings cover selection on the host, with no kernel calls. [First implementation](https://github.com/UwUCammie/VIctory-7900XTX/commit/4eafaf72)

The candidate keeps the scan unless at least 128 requests have already been collected and at least 128 inputs are left. Both versions can be checked with their respective source checkout.

```sh
python -B benchmarks/write_watch_ranges.py PATH_TO_CHECKOUT
```

The adaptive implementation also agreed on all 400 generated sequences. Its 4,096 shuffled disjoint inputs took 7.23 ms versus 0.46 ms, and 512 mixed inputs took 13.10 versus 11.52 µs. At 64 mixed inputs it took 356 versus 366 ns. At 4,096 nested inputs only one request survived and the time moved from 2.34 to 3.09 µs. These are eight alternating pairs from a second run of the native fixture. Four range and journal tests and one write-watch generation test passed with the exact MSVC build under Wine 11.22. [Adaptive implementation](https://github.com/UwUCammie/VIctory-7900XTX/commit/968673d7)

### Avatar Wine profile from PR #440

The upstream report uses samples from seconds 140–240 in the first scene on a Radeon RX 7900 GRE. Its fastest runs precede the merge from Avatar main. I staged that profile from `b2bf3d99`, using the existing 1280×720 scene and 3840×2160 interface patch, a trace of successful presents, and Beqren's release-build input patch. The initial release executable ignored `VICTORY_KEYS`, and private captures from the interrupted launch still showed the start prompt at 40 s. The corrected build uses the same input sequence as the other cold runs. The test uses the local RX 7900 XT Wine 11.22 setup, vkd3d-proton `71cae091`, a 4 GiB limit for card buffer copies, and an empty story and five empty cache directories. The 300-second scoring interval begins at launch. The launch configuration and runtime flags that can be verified from the log are in `avatar_wine_profile.py`. Timing and private visual validation are pending. [Upstream measurement](https://github.com/avatarmanz/VIctory-7900XTX/pull/440), [Local runtime source](https://github.com/UwUCammie/VIctory-7900XTX/commit/86c904b1)

The first corrected launch confirmed the 60 Hz title setting, Wine `mmap`, private graphics pages and the 10,000 ms compute budget. Before it yielded to a parallel build at 99.24 s, the runtime reported 379 compute waits above 100 ms. In 29 reports the pipeline still had no result when the wait ended. The longest reported wait was 10,000 ms. The reports can overlap across threads. The follow-up keeps the same executable, inputs, drivers and flags and changes only `VICTORY_COMPUTE_WAIT_MS` from 10,000 to 500. Compare both full cold launches and review faces privately before drawing a conclusion.

The #440 author also reported a one-run first-scene comparison of 25.1 and 22.6 ms per frame with Belobug #477's write-combined memory path. I staged their premerge source with the same 720p output, interface and input patches. Both cold arms use that executable and enable `VICTORY_WC_STATS`. Only `VICTORY_WC_NO_BACK` changes. The runtime still copies back short ranges, unwatched copies and copies outside card memory. The enabled-arm counters verify whether any qualifying declarations took the alternate path. The timings keep the read census off in both arms. CPU read coverage and saved-scene visual checks need separate runs. [First-scene report](https://github.com/avatarmanz/VIctory-7900XTX/pull/440#issuecomment-7213680361), [write-back patch](https://github.com/Belobug/VIctory-Belobug-AMD/pull/477), [local test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/6416fd02)

The first complete `86c904b1` run started a new story with all five caches empty. It used a Radeon RX 7900 XT, RADV 26.3.1, Wine 11.22 and vkd3d-proton `71cae091b06571e`. The release executable matched 171 PDB source checks. The guard excluded seven earlier interruptions. The 4 GiB card buffer cap and 10,000 ms compute budget were active for this measurement.

| Wall-time window | Accepted presents | Average FPS | P99 gap | Longest gap | Time in gaps over 100 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0–300 s from launch | 6,579 | 21.93 | 172 ms | 19.935 s | 142.32 s |
| 140–240 s from launch | 2,006 | 20.06 | 147 ms | 9.477 s | 46.41 s |

The first accepted present came at 2.19 s. The 300-second window contains 619 reports of compute waits above 100 ms, including 38 with the result cell still empty when the wait ended. The longest present gap, from 47.97 to 67.90 s, contains 13 of the latter reports. The waits can overlap across threads. They establish that pipelines were still outstanding during the gap.

In the private 720p samples, the man's face rendered at 85 s. The driver's skin was missing at 160 and 175 s, with the eyes and teeth visible. Subtitles were centered in the samples at 85, 175 and 235 s. The facial deformation pass named in the upstream investigation had a 9.978 s wait without a pipeline result at 77.98 s. This run establishes the symptom. Identifying the operation that caused it here requires further evidence.

The first 500 ms trial yielded at 114.45 s. In the first 100 s, which preceded the overlap, it accepted 1,910 presents versus 1,489 in the 10,000 ms control. The longest gap in that prefix fell from 19.93 to 10.93 s. Compute wait reports without a pipeline result rose from 36 to 246. The executable, driver files, input and other runtime flags matched, and both budgets were confirmed in the logs. The earlier two face samples showed skin in the 500 ms run. It ended before reaching the car comparison. The full cold pair is pending.

A later 500 ms retry reached the car before yielding at 209.68 s. Its first 200 s used the same executable, driver files, input, initial caches and other flags as the 10,000 ms control. The longer-wait run accepted 3,602 presents with a 201 ms P99 in that interval. The shorter-wait run accepted 4,579 with a 561 ms P99. The longest gap fell from 19.93 to 10.93 s, and compute wait reports that ended without a result rose from 36 to 310. In a similar front view of the car around 175 s, the driver had missing skin with either budget and the passenger lost his facial skin with the 500 ms budget as well. The 500 ms attempt ended before a full cold-boot score could be recorded.

The next compute tests use the same 10,000 ms wait. The sole switch is `VICTORY_EARLY_COMPUTE_MAX_BYTES`, which starts eligible compute pipelines at creation, before their first dispatch. A 1 KiB limit restored skin in matched diner shots on an earlier build. The new runs check the cutoff in the log, confirm that an eligible pipeline actually took the early path, and measure the entire first 300 s with visual checks in the car. [Earlier skin comparison](https://github.com/UwUCammie/victory-amd/commit/6606f6d7), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/bbf71d6e)

The port passed all seven pipeline tests under Wine. Two control launches with the same executable, zero-byte limit, 10 s budget, vkd3d-proton `71cae091b06571e` and scripted inputs reached matching shots before yielding at 186.11 and 226.00 s. The first showed both faces in the car. The second showed the driver's eyes and teeth without skin at the same line of dialogue. Only the second logged a wait that ended without the facial-deformation pipeline, after 9.955 s. The affected pipeline's input falls between 2 and 2.5 KiB, above the earlier 1 KiB cutoff. The next full comparison tests a 2.5 KiB cutoff against zero on the same executable. The separate 1 KiB case remains queued.

The #440 author reproduced the shorter-wait tradeoff with empty caches on a 7900 GRE and changed the upstream Wine default to 500 ms. The earlier 17 successful face runs had a populated vkd3d-proton cache. Another commit in the same update keeps 30 Hz pacing for the opening animation and moves to the requested faster interval once a frame reaches the configured draw count. I staged that commit separately from the compute tests. Our accepted-present counts include repeated images, so the pacing change needs its own capture check and full cold timing. [Upstream retest](https://github.com/avatarmanz/VIctory-7900XTX/pull/440#issuecomment-7214168214), [Pacing test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/8985db60)

The 2.5 KiB run made the facial-deformation pipeline at 2.54 s and showed both faces in the private car samples. Over the first 220 s it accepted 4,143 presents versus 3,853 on the same executable with early compilation off. P99 went from 200 to 220 ms. The longest gap remained about 20 s. The enabled run logged device removal at 261.92 s. The overlap guard fired 658 ms later, so the full run is excluded. The launcher now preserves a timestamped device loss that precedes an overlap marker. The next wait-budget test keeps the 2.5 KiB cutoff and changes only the 10 s compute wait to 2 s.

Another 2.5 KiB launch made the same pipeline at 2.63 s and also showed both faces, including the matching driver close-up. This run yielded to a parallel build at 253.70 s. Its repeated visual result supports moving the 2 s trial ahead of the remaining 10 s retries. Full 300 s timing is still pending for both settings.

The first two 2 s attempts yielded to parallel builds at 163.39 s and 252.53 s. The second made the facial-deformation pipeline at 2.65 s. Both faces showed skin in the car at 175 s, and the driver's close-up at 160 s showed skin and a centered subtitle in the first attempt. These samples cover face visibility. Lip motion and indoor lighting still need separate checks.

The second 2 s attempt and the 10 s attempt that yielded at 253.70 s had the same executable, three driver file digests, loaded vkd3d-proton build, five initially empty caches, new story, 720p output, input and 2.5 KiB cutoff. The first 245 s precede either overlap marker.

| Compute budget | Accepted presents | P99 interval | Longest gap | Time in gaps above 100 ms | Reported waits without a pipeline result |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 s | 4,752 | 223 ms | 17.828 s | 130.23 s | 36 |
| 2 s | 5,312 | 294 ms | 11.918 s | 118.22 s | 125 |

Both fixed windows include launch and stutters. The 2 s trial had a shorter maximum gap and more missing pipeline results at the end of a reported wait. Its P99 was higher in both interrupted attempts. Accepted presents can repeat an image and concurrent wait notices can overlap. Both runs are excluded from the full 300 s score.

I also staged an independent comparison of the shared completion notification against per-pipeline notifications. The latter wakes only threads waiting on the pipeline that completed, including when a failed compile is handled. The same-binary experiment keeps the 10 s budget and 2.5 KiB cutoff and checks the active notification setting in the log. [Source change](https://github.com/UwUCammie/VIctory-7900XTX/commit/16805bb1), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/fd1b42e0)

The 2 s compute trial still used the separate 10 s wait for passes over the screen. I reconstructed the reported waits from their end times and durations and clipped them to complete present gaps. Within each category, overlapping thread intervals count once. The categories can overlap in wall time, and the intervals show where each wait was active.

| Gap start after launch | Present gap | Overlap with screen waits | Overlap with compute waits |
| --- | ---: | ---: | ---: |
| 47.88 s | 11.918 s | 11.913 s | 2.986 s |
| 59.94 s | 10.469 s | 10.000 s | 2.622 s |
| 37.72 s | 9.978 s | 9.978 s | 2.000 s |
| 70.50 s | 5.949 s | 5.831 s | 2.075 s |

One mesh/pixel pipeline repeatedly hit the screen wait limit in both budgets. Its two stages total 5,088 bytes. The next comparison queues existing screen-pass candidates up to 6 KiB at creation on the normal early workers. Both arms keep the 10 s screen wait, 2 s compute wait and 2.5 KiB early compute cutoff, using the same binary and cold protocol. The existing reserved workers still take requested passes. Check the full timing and private matching visuals before recommending the setting. [Proposed change](https://github.com/UwUCammie/VIctory-7900XTX/commit/59241786), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/c97188bd)

The first write-back control yielded to a parallel build at 221.18 s. It used the staged driver and logged 29 write-combined statistics intervals and zero kept-declaration intervals before 210 s. A complete same-binary control and candidate remain necessary for a write-back result.

The fourth write-back control also yielded, at 197.75 s. The driver's skin was missing in the private car close-up at 160 s and the passenger's face was visible at 175 s. The runtime logged decoration-bake draws from 24.50 s and a successful wait for the tracked facial-deformation pipeline at 76.44 s. Those events show that pipeline was available by the car shot. They leave open whether an earlier dispatch was missed and whether the already recorded bakes affected this face. Keep this sample outside the 300 s timing result. [Related loading-rate investigation](https://github.com/avatarmanz/VIctory-7900XTX/pull/449)

The RX 7900 GRE report identified a group of four compute programs used in facial deformation. Two stages in that group fit the 2.5 KiB cutoff, and the next is 2,704 bytes. In our 2 s repeat, the two eligible programs finished compiling at about 2.65 s. The 2,704-byte program still had waits that ended without a result. Both faces showed skin in the sampled car shot. The largest of the four is 9,748 bytes. In each of three launch traces, raising the cutoff from 2.5 KiB to 3 KiB would cover 55 more distinct compute shaders observed at first bind. The next cutoff comparison uses 2.5 and 3 KiB at the same 2 s compute wait on the same executable. [Independent facial-deformation trace](https://github.com/avatarmanz/VIctory-7900XTX/pull/449#issuecomment-7215519917)

The local serial queue rotates the write-back, screen and 2 s compute-cutoff trials after a guard-marked interruption. Within those entries it picks the least recently launched eligible trial. A fresh attempt still needs new story slots, empty caches and the full 300 s window. The write-back candidate still waits for a qualifying control. A renderer failure follows the failure path. Trial order is reconstructed from the existing launch files, so the queue can advance at a safe boundary without another scheduler or a reset of active runs.

The first early-screen control yielded at 242.74 s. Before 220 s it accepted 4,509 presents, with a 12.47 s maximum gap almost fully covered by screen waits. The driver's skin was visible in the matched car close-up. The next run used the same executable and three driver DLL digests, 720p scene, 4K interface, inputs, new story and five empty caches. Its only changed flag was the screen limit. It logged the 6 KiB cap and first early screen work at 1.88 s, then yielded at 20.78 s, before the screen stalls seen in the control. Both runs are excluded from 300 s scoring. The rotation advanced after each yield. [Early-screen change](https://github.com/avatarmanz/VIctory-7900XTX/pull/450)

`cold_boot.interrupted_prefix()` checks a completed run's timestamped overlap marker and requires a present beyond the requested cutoff and before the guard. It checks the cold launch metadata, rejects runtime failures, and can verify the same host output, interface and driver as the full report. It labels its results as diagnostic prefixes. The full scorer still rejects interrupted runs.

The 6 KiB screen retry first queued eligible work at 1.79 s and yielded to a separate build at 144.62 s. The shared 140 s prefix had 2,767 accepted presents with the cutoff off and 2,593 at 6 KiB. P99 was 238 ms off and 874 ms at 6 KiB. The longest gap decreased from 12.47 s to 10.13 s, with screen waits covering nearly all of both gaps. The executable, three driver DLLs, input, initial caches and remaining flags matched. The shorter single gap came with more long holds over the measured prefix. Both attempts are excluded from the full cold score.

A second 6 KiB attempt reached 144.82 s and then yielded to another build. Its first 140 s accepted 2,829 presents, with 252 ms P99, a 13.01 s longest gap and 73.57 s in gaps over 100 ms. A second off run using the same executable and settings through 140 s accepted 2,534 presents, with 272 ms P99, a 13.09 s longest gap and 79.13 s in gaps over 100 ms. One 6 KiB repeat landed between the two off runs for total hold time, and the other spent 0.63 s less in holds than the faster off run. The longest gaps and P99 vary across attempts. The 300 s comparison is still pending.

In the qualifying 21.93 FPS reference, 142.32 s fell in gaps longer than 100 ms over the full 300 s. Completed compute-wait reports overlap 114.60 s of those gaps, and screen-wait reports overlap 30.58 s. Their union is 123.61 s. The measurements clip completed waits to the scoring window and count coincident waits once. They measure overlap with stalls and cannot establish how much time a scheduler change would save.

That trace logged 1,047 successful compute pipeline completions with distinct shader keys. This gives little reason to prioritize deduplicating successful compute creations in this route. The indexed-use test applies the earlier translator change to the exact Wine reference source. It builds an index of arithmetic readers and phi inputs on the first descriptor query, replacing repeated walks of the same shader during lowering. The comparison uses the existing 21.93 FPS control and changes only this translator source file. [Original optimization](https://github.com/jtrudeau1530/VIctory-7900XTX/pull/6), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/e1309cb7)

The two exact Wine source trees produced identical outputs on the native 256-input slice. The check compared DXIL bytes and host shader metadata for 254 translations, and verified two matching terminal errors across eight alternating runs. Native release medians for summed translation time were 2.98 s before and 2.48 s after. Wall medians were 1.39 s and 1.14 s. The native probe used the RDNA path with a 64-lane maximum and otherwise default translator settings. This measures translation on the sampled inputs. The Windows release build is staged separately for the full cold gameplay comparison. [Wine branch PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/3)

The first indexed gameplay attempt verified 171 runtime source checksums, used all five empty caches and loaded vkd3d-proton `71cae091b06571e`. Its driver file digests, runtime flags and route matched the reference. It yielded to a separate build at 33.51 s, with its final accepted present at 26.44 s. The run is excluded from full scoring and lacks a strict 30 s prefix.

A later indexed run yielded to another build at 100.08 s. The first 90 s qualified as a diagnostic comparison against the reference. The driver files, loaded vkd3d revision, flags, input, five empty caches and fresh story profile matched. The reference had 1,473 accepted presents and the indexed build had 1,514. P99 intervals were 201.57 ms and 353.27 ms. Time in gaps longer than 100 ms was 64.91 s and 63.99 s. Waits with shader translation still pending overlapped 53.51 s and 45.53 s of complete gaps of at least one second, while waits after the last logged translation overlapped 24.63 s and 29.31 s. The indexed run recorded 24 compute wait reports without a pipeline result, compared with 36 in the reference. A full run is still required to measure the gameplay effect.

A separate cache change reuses the in-memory translation after successful atomic publication. The existing read path still handles cache hits, stale source tags and damaged entries. The reference had 2,848 shader cache entries totaling 182.8 MB at exit. Three focused Windows MSVC cache tests passed on Wine 11.22 with 111 runtime source checksums. The game comparison uses the same reference settings and changes the cache code alone. [Wine cache PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/4), [Cold comparison source](https://github.com/UwUCammie/VIctory-7900XTX/commit/329ca9bc)

The first cache candidate verified 171 runtime source checksums and yielded to another build 4.80 s after launch. The full cold result remains pending.

The single-parse experiment passes the renderer's parsed console program to the shader translator on a miss. The cache still uses the original bytes, including padding, and retains the existing failure and retry rules. Native release probes compared the two paths on 256 inputs over four runs each. All 254 translations matched for DXIL, host metadata, native code and binding metadata. The two terminal errors also matched. Median summed time was 3.024 s with separate parsing and 3.001 s with shared parsing. Median wall time was 1.406 s and 1.408 s, respectively. The padding and missing-part regression passed. The native sample showed no meaningful speed gain. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/778138a1)

The priority gameplay comparison now builds the indexed translator together with the fresh-cache path. Both changes use the exact source already validated in their individual tests. The combined candidate differs from the reference only in the two source files. It requires the original runtime flags, private driver digests, resolution and route, five empty caches and all 300 seconds from launch. [Combined experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/2d6e4f31)

The combined build verified 171 runtime source checksums and yielded to another build at 83.84 s. Its executable differed as planned and its runtime flags, input, five empty caches and all three driver file digests matched the reference. It loaded vkd3d-proton `71cae091b06571e`. The strict first 80 s prefix qualifies as diagnostic evidence.

| Build | Accepted presents | P99 interval | Longest gap | Time in gaps above 100 ms | Compute pipelines completed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reference | 1,444 | 91.69 ms | 19.93 s | 56.02 s | 768 |
| Combined shader changes | 1,481 | 210.81 ms | 10.69 s | 54.81 s | 808 |

Full 300 s scoring excludes the interrupted launch. The trial remains in rotation.

The second combined attempt reached 159.65 s before yielding to another build. Its first 150 s qualified as a diagnostic comparison with the reference. The exact executable and PDB matched 171 source checksums. Both runs used the same driver files and loaded vkd3d-proton revision, flags, inputs, scene and interface dimensions, five empty caches and a fresh story profile.

| Build | Accepted presents | P99 interval | Longest gap | Time in gaps above 100 ms | Compute waits without a result |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reference | 2,440 | 250.90 ms | 19.93 s | 91.71 s | 36 |
| Combined shader changes, second attempt | 2,908 | 223.17 ms | 20.06 s | 79.55 s | 26 |

Waits on groups with a translation still pending overlapped 63.68 s of complete gaps of at least one second in the reference and 47.63 s in the combined build. Overlap after the last translation was logged was 32.96 s and 34.38 s, respectively. This run leaves the full 300 s result and visual check open.

The fourth combined attempt yielded to a competing build at 233.41 s. The first 230 s passed the same cold-start checks. The reference and candidate used the same input, flags, caches and driver files, and both loaded vkd3d-proton `71cae091b06571e`. The Windows release candidate matched 171 runtime source checksums. The guard was the first interruption.

| Build | Accepted presents in 230 s | P99 interval | Longest gap | Time in gaps above 100 ms | Compute waits without a result |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reference | 3,934 | 226.09 ms | 19.93 s | 129.42 s | 38 |
| Combined shader changes, fourth attempt | 4,724 | 205.53 ms | 20.09 s | 112.00 s | 22 |

Waits with a translation still pending overlapped 86.24 s of complete gaps of at least one second in the reference and 66.35 s in the candidate. After the last logged translation, overlap was 48.80 s and 47.17 s. All stalls from launch count in these prefixes. The candidate still needs a complete 300 s run and a matched visual check.

The updated Wine branch at `3f9ac64e` includes the card-step copy guard and the large worker-pool recovery fix. The new reference carries the accepted-present trace, 720p interface overlay and release input script. The shader comparison adds the same indexed translator and fresh-cache changes. Expected runtime flags and cold-start checks remain the same for both runs. They build in one detached checkout with a lock through the executable and PDB verification, so Cargo can reuse unchanged artifacts between revisions. [Updated reference](https://github.com/UwUCammie/VIctory-7900XTX/commit/54750a3a) and [shader candidate](https://github.com/UwUCammie/VIctory-7900XTX/commit/fd9520ad).

The first updated reference verified 175 runtime source checksums and yielded to a separate build at 40.82 s. The first 35 s had 1,450 accepted presents and 11.03 s in gaps over 100 ms. The earlier reference matched its driver files, actual loaded driver, input, output, runtime flags and five empty caches. Its first 35 s had 1,436 presents and 11.02 s in gaps over 100 ms. These windows end before the later cold shader stalls. The updated reference and shader candidate remain in the full-run queue.

The shader candidate reused 95 of 99 Cargo artifacts in the pinned checkout. The MSVC release build took 90 seconds compared with 125 seconds for the clean reference build. The binary and PDB independently matched all 175 source checksums. The candidate booted with the same flags, driver files, input, 720p scene and 4K interface, and yielded at 10.67 s. The build times are independent of gameplay timing.

Wine head `37210307` combines the d16 descriptor fix, half views and raw typed loads for facial animation. The 720p candidate carries the same two compiler and cache optimizations as the preceding build. It keeps raw typed loads enabled and uses the original cold launch settings. [Wine face candidate](https://github.com/UwUCammie/VIctory-7900XTX/commit/bb5b6f7a)

The raw-load setting already reaches the shader cache key through the translator's host settings. A generated test launched the same executable three ways. The explicit on setting and the default had identical keys, and the disabled setting had a distinct key. All four shader-cache tests passed with the Windows MSVC build under Wine 11.22. The face candidate uses the upstream cache key unchanged. [Cache-key test](https://github.com/UwUCammie/VIctory-7900XTX/commit/e09666d3)

The first face candidate matched 176 runtime source checksums and yielded to a parallel build at 75.62 s. The first 70 s had 1,446 accepted presents, compared with 1,442 in the earlier release on the same route. The longest pause was 19.50 s versus 19.93 s. Time in pauses over 100 ms was 45.86 s versus 46.02 s. Both runs loaded the same vkd3d revision, with matched driver files, input, five empty caches, and 720p scene and 4K interface. This compares different Wine revisions over a short prefix.

In a private capture in the opening street scene, one character's head was black with only the eyes and teeth visible. The short run supplied no matched dialogue sequence for checking lip movement. The follow-up build starts compute pipelines up to 3 KiB at creation, using the same 10 s compute wait budget and the same face source. This tests the first-use scheduling hypothesis separately. [Early compute candidate](https://github.com/UwUCammie/VIctory-7900XTX/commit/d34baace)

The first 3 KiB run confirmed early compute was active at 1.88 s and yielded to another build at 80.54 s. The three tracked programs within the cutoff had host pipelines by 2.55 s. The fourth was ready by 29.33 s. The control had all four ready by 66.19 s. In private captures from the same opening dialogue and subtitle line, the 3 KiB build showed both faces, while the woman's face was missing in the control. The camera progressed further in the 3 KiB capture.

Both first-70-second windows matched the 10 s compute wait, other runtime settings, driver files and loaded revision, input, five empty caches, native 720p scene and 4K interface. The control and 3 KiB run had 1,446 and 1,452 accepted presents, respectively. The longest pause was 19.50 s and 10.49 s, P99 was 60.65 ms and 100.78 ms, and time in pauses over 100 ms was 45.86 s and 45.83 s. This is a short cold diagnostic comparison. The full retry is queued, alongside a test of a 2 s wait on the same early-compute executable.

The 10 s retry yielded to a concurrent build at 71.76 s after 1,446 presents in the first 70 s. The 2 s attempt also yielded, at 22.80 s before the first sustained pause. The 0-byte and 3 KiB cutoff arms now use the same executable and a 10 s wait, and both require the runtime to report the requested byte limit. This will isolate the cutoff from the executable change in the first comparison.

The matched 0-byte control reproduced the missing skin in the same street dialogue shot. The 3 KiB run showed the face at the same dialogue line. The binary, 10 s wait, driver files, input and cache setup were identical. Each run was interrupted by a parallel build after the first 70 s, so the full cold average remains pending.

A second matched pair extended the common cold window to 105 s. With the cutoff off and at 3 KiB, the runs accepted 1,596 and 1,876 presents, spent 75.46 and 66.88 s in gaps over 100 ms, and had longest gaps of 20.09 and 11.07 s. P99 was 1,063 and 265 ms, respectively. The same executable, driver files, loaded driver, launch flags apart from the cutoff, input, no saved story and five empty caches were verified. Both used ten general workers, the 10 s compute wait, a native 720p scene and a 4K interface. Parallel builds ended the runs after 107.77 and 146.28 s. Both showed visible skin in the same side view during dialogue. The frontal close-up used a different angle in the run with the cutoff off, so this pair leaves that visual comparison open.

| First 70 s | 0 bytes | 3 KiB, first attempt | 3 KiB, second attempt |
| --- | ---: | ---: | ---: |
| Accepted presents | 1,438 | 1,452 | 1,446 |
| P99 present interval | 38.84 ms | 100.78 ms | 91.14 ms |
| Longest present gap | 20.05 s | 10.49 s | 11.00 s |
| Time in gaps over 100 ms | 46.21 s | 45.83 s | 46.01 s |

The first dispatch trace ran with the cutoff off and the 10 s wait. Another build interrupted it at 63.37 s. In the first 60 s, all four selected compute shaders were requested. Three recorded their first dispatch by 28.24 s. The fourth was requested twice without a ready pipeline and had no recorded dispatch in that window. The trace measures command-list recording. The queued diagnostic repeats the measurement with a 3 KiB cutoff on the same executable. [Wine PR update](https://github.com/borntofrag34/VIctory-7900XTX/pull/11#issuecomment-7220506173)

The next pipeline creation experiment hashes the borrowed translation bytes directly and queries the host's anisotropic point-mip capability once. It keeps the same hash inputs, including an empty slice for a missing stage, and passes the same shader bytes to the driver. The Windows checks and matched cold run are queued with the 3 KiB cutoff and 10 s wait. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/31127dcf)

Six focused Windows MSVC tests passed under Wine on this integration, with 112 verified runtime source checksums. The optimized release matched 176 runtime source checksums and yielded to a parallel build at 89.04 s. Its first 75 s and the earlier 3 KiB control used the same inputs, loaded driver, three driver binaries, runtime settings and five initially empty caches. Both accepted 1,463 presents. The longest gap rose from 10.49 s to 19.88 s, P99 fell from 186.52 ms to 116.78 ms, and time in gaps above 100 ms was 50.54 s and 50.59 s. The face was visible in the same street dialogue shot. The matched prefix shows no throughput gain. [Wine PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/12)

An opt-in dispatch trace records whether selected direct and indirect compute calls reached the host command list. It reports first attempts, reasons that recording stopped, and the first successful recording. It keeps the first-success report even after eight rejections, exercised by a focused Windows MSVC test under Wine 11.22 with 113 runtime source checksums verified. The 95 s diagnostic run uses the original cold settings and is excluded from FPS scoring. The report summarizes counts and timings and measures record-time behavior. [Dispatch trace source](https://github.com/UwUCammie/VIctory-7900XTX/commit/f00c43cb)

An experimental index for half-view shader analysis preserved shader bytes, binding metadata and error results across eight alternating native passes. In a stratified 256-input sample, 254 translated and summed median time was 2.751 s before and 2.814 s after. A separate 2,048-input discovery slice yielded four shaders with half views. Their summed medians were 1.633 ms before and 1.656 ms after. The index showed no speed gain in either sample, so the current gameplay candidate uses the original analysis. [Experimental index](https://github.com/UwUCammie/VIctory-7900XTX/commit/dae694e2)

Grouping completed waits by shader list and compute or screen class shows how concentrated the long stalls were. The exact reference had 30 complete present gaps of at least one second, totaling 122.44 s. Logged waits overlapped 120.96 s. Taking the largest group in each gap accounts for 72.15 s, including 46.49 s in the first 80 s. Three of the first four gaps in that window were at least 80% covered by a single group. The combined shader changes had seven gaps of at least one second in the same window, totaling 49.46 s versus the reference's 51.07 s. The sum of the largest group's overlap in each gap fell from 46.49 s to 35.88 s. Later reference gaps were spread across more groups. Group identity uses logged shader lists, which can be shared by different pipeline configurations. Overlap measures timing and does not establish how many seconds a compiler change can remove.

The same complete gaps can be attributed by the timestamp of each wait's last shader translation. In the full reference, waits for shader groups with a translation still pending overlapped 90.82 s. Waits after all their shader translations were logged overlapped 51.79 s. These intervals overlap when multiple threads wait at once. The first 80 s reference and combined prefixes respectively had 49.30 s and 41.23 s of overlap while translation was pending, and 19.84 s and 25.76 s after translation was logged. Both traces supplied translation markers for every shader in their logged waits. A pending translation includes any time spent waiting for a worker to begin. The timestamps alone cannot divide that interval into queue time and translator execution time.

For successive builds, `build_checkout.py` pins a separate detached worktree at the desired source revision and holds a lock through the command. A stable path allows Cargo to reuse unchanged artifacts. The runner rejects dirty checkouts and keeps the existing executable/PDB source validation before gameplay. A synthetic Git test switched the worktree between two commits and confirmed that a local edit was preserved. In a Windows MSVC test build, switching from the test-only remap control to the fix reused 82 of 83 Cargo artifacts. The build finished in 4.52 s, and the executable and PDB matched 162 source checksums for each revision. These are build measurements.

The current queue lets both priority workers take compute, including when an urgent screen pass arrives while both are busy. The next comparison reserves one of those workers for requested screen passes and leaves the other shared. Shared workers keep their existing FIFO order. The policy keeps the same worker count, 2 s compute budget, 10 s screen budget and 2.5 KiB early compute cutoff in both arms. Early screen work is off. Ten focused Windows MSVC tests under Wine passed, with 108 source checksums in the exact test executable's PDB. They cover the reserve and both claim orders without a duplicate compile. The gameplay verifier requires a first claim on the reserved arm. [Candidate source](https://github.com/UwUCammie/VIctory-7900XTX/commit/cc3b85bb)

The first reserved-worker launch claimed a screen pass at 26.45 s and lost the GPU device at 89.10 s. The guard recorded no overlap. The shared control yielded to a separate build at 4.81 s. The runs matched the executable, all three driver digests, new story, five empty caches, inputs and flags except for the worker switch. The driver actually loaded `71cae091b06571e` in both arms. These runs establish that the reserved worker took a pass and that the renderer lost its device. A complete shared control is pending, and the reserved setting remains held.

The separate Wine watcher fix handles a configured pool of 64 general and two priority workers. A Windows MSVC regression under Wine 11.22 reproduced the single wait failing on 66 real thread handles, then verified two bounded waits that covered all handles once. This test runs without the title. [Worker recovery PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/2)

The first 3 KiB trial got the 2,704-byte facial-deformation pipeline ready at 2.51 s, before its first recorded bind at 56.77 s. In the selected 2.5 KiB trial that pipeline first bound at 50.92 s and finished at 76.66 s after resultless waits. Both runs used the same executable, five initially empty caches, new story, three driver digests, input, 720p scene and 4K interface, with a 2 s compute wait. The sole changed setting was the cutoff. The 3 KiB arm yielded at 59.61 s, before a matched car shot. The first 50 s had 1,469 and 1,460 accepted presents at 2.5 and 3 KiB, respectively. Both arms are excluded from 300 s scoring.

The existing Radeon late-fill test is also staged on the current Avatar Wine build. The port keeps the Wine placement order and checks learned pages only after the planner finds a submission it could take. It uses an explicit off/on option on the same executable, a disposable copy of the indoor save, vkd3d-proton `71cae091`, and the 720p Wine profile. The two fixture paths cover bytes read by the card and by the CPU. Saved-scene and first-boot results require separate observations. [Upstream geometry fix](https://github.com/avatarmanz/VIctory-7900XTX/pull/434), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/f13ccad4)

The exact Windows MSVC Wine port passed nine focused tests, including the generated CPU and GPU fill comparisons using distinct live pages. The separate flight test passed on the RX 7900 XT with learning off and on under Wine 11.22, RADV 26.3.1 and vkd3d-proton `71cae091b06571e`. The PDB matched 108 runtime source checksums. The saved pair records the input and save digests and checks that only the learner switch differs before matching camera intervals. Gameplay rendering remains unverified for this port.

The saved geometry arms can rotate with the cold trials after an interruption. The guard and saved runner share a timestamped marker, and the earliest marker survives concurrent observations. The queue uses the saved launch marker for rotation and keeps saved results outside cold scoring.

Write-back control attempt 8 lost the device at 264.32 s with write-back disabled. The wrapper exited at 265.51 s and the guard recorded no overlap. The renderer reported `DXGI_ERROR_DEVICE_REMOVED` and the driver logged `VK_ERROR_DEVICE_LOST`. The earlier early-compute failure at 261.92 s reported the same errors on a different executable. These errors do not identify the command or resource responsible. The queue holds the write-back pair for now and records the time of a device loss even when the process exits before a guard interruption.

The separate fault probe uses the same release executable and write-back-disabled profile, with vkd3d-proton's fault and breadcrumb flags requested. The game's DRED option is inactive in that release build. The probe records the requested driver configuration and is explicitly excluded from full scores and diagnostic prefix timing. Any command or allocation details remain in private logs. [vkd3d-proton breadcrumb documentation at the tested revision](https://github.com/HansKristian-Work/vkd3d-proton/blob/71cae091/README.md#breadcrumbs-debugging)

The first fault probe yielded to a parallel build at 202.54 s, before either recorded failure time. The updated Wine PR has a guard from #351 that drops individual out-of-range copy commands. Its caller could still mark a skipped step as taken and redirect a slot to scratch that was never filled. The follow-up checks both halves of every planned copy and the staging range before creating a list or recording shadow changes. If a range fails, the whole speculative batch returns to the existing waiting path. The physical RX 7900 XT flight fixture checks a valid earlier copy and an invalid later destination before exercising the normal in-bounds route. Ten focused Windows MSVC Wine tests and the separate flight test passed, with 111 PDB source checksums. The replacement write-back control and candidate use a new matched executable and keep the original failures excluded. [Source follow-up](https://github.com/borntofrag34/VIctory-7900XTX/pull/1), [Cold test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/1b3ab197)

The 3 KiB repeat compiled the additional facial-deformation pipeline at 3.14 s and first bound it at 64.31 s. The driver’s skin was visible in the private car close-up at 160 s. The two cutoffs had 2,855 and 2,868 accepted presents over the first 160 s, with P99 of 502 and 881 ms and longest gaps of 11.92 and 12.05 s, respectively. The 3 KiB arm had 92 reported waits without a result versus 101 at 2.5 KiB. The interrupt at 162.87 s excludes this repeat from the full score. These results show that the extra pipeline consistently compiled early, with comparable present counts and a longer tail in this pair.

A later 3 KiB run reached 151.68 s before yielding. Its strict 150 s prefix had 2,714 accepted presents, 597.16 ms P99, a longest gap of 10.55 s, and 85.91 s in gaps above 100 ms. The same 150 s window in the other qualifying prefixes had the following results. All five used the same executable, driver files and revision, input and fresh profile at 1280×720, with a 4K interface and five empty caches. The only setting changed across the two groups was the size cutoff.

| Cutoff | Attempt | Accepted presents | P99 interval | Time in gaps above 100 ms |
| --- | ---: | ---: | ---: | ---: |
| 2.5 KiB | 1 | 2,358 | 1,374.25 ms | 95.08 s |
| 2.5 KiB | 2 | 2,521 | 1,273.35 ms | 90.98 s |
| 2.5 KiB | 5 | 2,683 | 767.52 ms | 87.06 s |
| 3 KiB | 2 | 2,648 | 1,247.92 ms | 87.74 s |
| 3 KiB | 5 | 2,714 | 597.16 ms | 85.91 s |

The latest 3 KiB run ended before the matching car shot. Run-to-run variation and the incomplete observations leave the full score and visual comparison open.

The replacement write-back control started with five empty caches and loaded vkd3d-proton `71cae091b06571e`. It yielded to a separate build at 121.18 s without a preceding device-loss event. The earlier losses occurred after 261 s, so the retry remains queued and there is no qualifying result for this pair.

The generated legacy MAD fixture for #454 reproduced a rounding mismatch on the RX 7900 XT with Wine 11.22, RADV 26.3.1 and vkd3d-proton `71cae091b06571e`. The executable and PDB matched 38 shader source checksums. With inputs `(1 + 2^-23)`, `(1 - 2^-23)` and `-1`, the stock result was `0x00000000`. One fused rounding gives `0xa8800000` (`-2^-46`). The driver's generated SPIR-V had one explicit `Fma`. Decorating its result with `NoContraction`, validating the fixture with `spirv-val`, and rerunning on the same executable and driver made all four cases pass. The driver cache was disabled in both diagnostic runs. The Wine gameplay comparison remains held pending a fix that works without a fixture override. [Upstream report](https://github.com/avatarmanz/VIctory-7900XTX/pull/454#issuecomment-7216444516), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/2d6dfec8)

### Boolean lowering in cold shader translation

A local CPU profile placed the boolean decision diagram's if-then-else operation among the next largest runtime symbols after the arithmetic-use scans. The experiment simplifies a branch that repeats the condition and interns new nodes in one map lookup. The native release probe compared the combined shader build with this one additional translator change. Eight alternating runs on a deterministic 256-input slice matched exactly for all 254 translations and both terminal errors, including generated DXIL and remaining host metadata. Median summed translation time was 2.599 s before and 2.550 s after. Median wall time was 1.227 s and 1.162 s, respectively. The translator suite passed 212 tests with two ignored. The sample suggests a small change in native translation time. A full cold comparison is queued behind the exact combined control. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/c39475eb)

### Descriptor arithmetic from long shader waits

The largest complete gap in the reference overlapped two waits for the same screen shader group. Its last translation was logged at 77.29 s, and the pipeline was logged 11 ms later. In the second combined run the largest gap overlapped two waits for a compute shader. Its translation was logged at 68.19 s and the pipeline 6 ms later. Those traces place the remaining work before the translation completed, including time before a worker starts the job.

The descriptor experiment classifies arithmetic and transfers when indexing readers and caches the answer at each remaining move depth. Two stratified 256-input passes matched all 254 outputs and both terminal errors, with median summed time changing by less than 1% in either direction. A separate private slice used the distinct stages from the most overlapping wait group in each of the ten longest complete gaps of each trace. The local scan found all 18 stages. Four alternating native runs per arm matched all 18 DXIL and host metadata outputs. Median summed translation time was 4.949 s and 4.944 s. This measured no meaningful speedup on the targeted inputs. The move-depth regression and the native translator suite passed with 212 tests and two ignored cases. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/41322ab9)

### Constant float comparison translation

The Wine port of Peppacodes's constant-compare fix passed 16 generated f16 and f32 cases on the RX 7900 XT under RADV 26.3.1, Wine 11.22 and vkd3d-proton `71cae091b06571e`. The cases cover equal, unequal and NaN inputs. The executable and PDB matched 38 source checksums. The port advances the translator version so a cached translation is regenerated. [Wine PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/8), [Upstream test report](https://github.com/avatarmanz/VIctory-7900XTX/pull/460#issuecomment-7218773303)

### Prioritizing pipeline requests with active waits

The opt-in scheduler experiment places a compute or screen request ahead of ordinary work while a title caller still has time left to wait. The original queue keeps ownership of each request, so hint expiry preserves the earlier order and a job can only be claimed once. Eight focused Windows MSVC queue tests passed under Wine 11.22 with the option off and on. The executable and PDB matched 108 source checksums. The 100 s timing diagnostic records how long requests wait before a worker claims them, with the priority option off. It is excluded from cold FPS scoring. The staged release matched 171 source checksums. Its first diagnostic launch confirmed the expected driver and setting, then yielded to another build at 32.46 s. The completed portion had 29 recorded claims and no compute wait reports, so it did not cover the stalls this test is intended to measure. Both full comparisons use the same binary with timing disabled and differ only in the priority option.

The second timing launch completed its 105 s timeout without overlap, with priority disabled. Its first 100 s contained 1,665 worker claims, including 990 that followed a request by more than 100 ms. The longest delay was 39.86 s. The trace matched all 342 compute wait reports to unique claims. Time before a worker claimed a matching job overlapped 30.97 s of complete frame gaps of at least one second. Waits can overlap, and queue time alone cannot establish how much time a scheduler change will recover. The matching 105 s launch completed without overlap with priority enabled. It used the same binary, driver files and loaded driver, input, timing instrumentation, cold caches and fresh story profile. The priority switch was the only runtime setting changed.

| First 100 s | Priority off | Priority on |
| --- | ---: | ---: |
| Recorded worker claims | 1,665 | 1,665 |
| Claims after 100 ms | 990 | 824 |
| Longest request-to-worker delay | 39.86 s | 40.60 s |
| Compute wait reports matched to a unique claim | 342 | 437 |
| Time queued before a claim overlapping complete gaps of at least 1 s | 30.97 s | 7.10 s |
| Accepted presents with timing enabled | 1,556 | 1,513 |
| P99 frame interval | 300.20 ms | 271.15 ms |
| Longest frame gap | 19.97 s | 10.36 s |
| Time in gaps above 100 ms | 72.76 s | 72.90 s |

Waits after the last shader translation was logged overlapped 26.60 s of complete long gaps with priority off and 52.58 s with priority on. The scheduler shortened the longest gap and moved more waiting after translation in this pair. Both launches remain diagnostic, with full 300 s comparison pending. [Experimental source](https://github.com/UwUCammie/VIctory-7900XTX/commit/b004cdec)

The same two queue traces had 19 and 12 additional claims eligible to wait for a shared unfinished translation. The estimated total was 0.470 and 0.421 worker-seconds respectively across the first 100 s. This estimate uses the worker claim and prior stage's translation completion as the earliest possible entry. It excludes the first eligible claim for each shader. The covered claims give little reason to change the queue around shared translations.

### Time after shader translation

The stage timing pair uses an 82 s diagnostic launch and checks the first 75 s to cover the three opening stalls more quickly. Each run remains outside cold FPS scoring. The priority-off launch verified 172 runtime source checksums, used five empty caches and the RX 7900 XT with RADV 26.3.1 and vkd3d-proton `71cae091b06571e`, and yielded at 38.03 s to another build.

The complete 10.37 s gap from 26.44 s to 36.81 s overlapped 9.213 s of driver compute pipeline creation, 1.040 s of queue residence and 0.005 s of root signature work. These are wall-clock intervals clipped to logged compute waits inside the gap. Different waits can overlap. The observation suggests looking inside driver creation for the first stall. It does not distinguish time actively compiling from time the calling worker was blocked or descheduled. [Stage timing source](https://github.com/UwUCammie/VIctory-7900XTX/commit/c5bf24c1)

The queued CPU diagnostic uses the same priority-off stage-timing executable and settings. It samples the Wine process for six seconds starting at process age 28 s. The profiling arm remains outside FPS scoring.

The second CPU diagnostic completed without overlap. The sample covered about 30.32–36.59 s after launch, inside the first 10.34 s present gap, and lost no samples. Of roughly 28,000 user-mode samples, 52.64% were in the Radeon Vulkan library, 33.63% were in unresolved executable mappings, and 3.91% were in vkd3d-proton's D3D12 core. Across the same sample, per-thread user and system counters attributed about 8.67 CPU-seconds per wall second to 12 pipeline workers and 1.28 to title threads.

The trace recorded 429 compute pipeline creation calls intersecting that first gap. Their clipped durations totaled 28.27 worker-seconds, with a peak of seven simultaneous calls. The stage traces and profiling data describe different kinds of work, so their totals cannot be added. The next cold comparison uses the same face build and 3 KiB cutoff with six, ten or fourteen general workers. The two priority workers and the compute wait remain fixed. Each arm checks the count the runtime reports.

`pe_perf_profile.py` checks the executable against the launch digest, matches its PDB and identifies the recorded anonymous mapping by the executable's aligned text section. All 6,908 anonymous pipeline worker samples were inside that section. Of those, 5,486 mapped to project source lines, with 3,782 passing through shader lowering. These counts are inclusive. The matched CPU diagnostic changes only the indexed operand lookup, keeping the tracing configuration, driver files and launch settings. [Indexed profiling build](https://github.com/UwUCammie/VIctory-7900XTX/commit/8c050aaa)

Both diagnostics completed without overlap. The corresponding CPU samples covered 30.32–36.59 s and 30.31–36.54 s from launch, inside the first long frame gap in each run. Counting each sample once per method, including inlined variants, gave the following comparison.

| Measure | Original lookup | Indexed lookup |
| --- | ---: | ---: |
| Samples through `computed_with` | 1,743 | 1 |
| Samples through `read_as_number` | 1,812 | 1 |
| Samples through shader lowering | 3,782 | 345 |
| First long frame gap | 10.345 s | 10.338 s |
| Accepted presents through 75 s | 1,448 | 1,471 |
| Time in gaps over 100 ms through 75 s | 50.97 s | 50.37 s |
| P99 present interval through 75 s | 42.29 ms | 107.13 ms |

The index removes most of the sampled operand lookup work. Radeon driver creation still dominates the sampled stall, with 60.42% of user-mode samples on the indexed build. The first long gap was effectively the same. The 75 s profiling windows remain diagnostic. The cold FPS score still requires 300 s on an unprofiled build.

The second updated Wine control and the second updated compiler/cache attempt both yielded to parallel builds. The first 65 s were clear in both. The arms accepted 1,438 and 1,442 presents, spent 41.10 and 41.05 s in gaps above 100 ms and logged 27 and 21 waits without a pipeline result. The compiler/cache attempt ran to 176.60 s before yielding. This matched prefix remains outside full FPS scoring.

Against the earlier verified 21.93 FPS release, the updated compiler/cache attempt accepted 3,105 versus 2,903 presents in the first 170 s and spent 87.22 versus 97.83 s in gaps above 100 ms. P99 increased from 226.09 to 245.92 ms. The driver files, input, runtime flags and initially empty caches matched. Several runtime changes separate these builds, and this longer prefix ends before the interruption. It cannot isolate the indexed lookup's effect or supply a five-minute score.

### General pipeline workers in the opening

The six-, ten- and fourteen-worker launches used the same Wine executable, input, three driver DLLs and loaded vkd3d-proton `71cae091b06571e`. Each used 1280×720 with a 4K interface, a fresh story, five empty graphics caches, two priority workers, a 3 KiB early compute cutoff and a 10 s compute wait. The runtime reported the requested general worker count. Separate builds interrupted the three launches at 208.78 s, 80.54 s and 60.81 s, respectively. Every prefix below ended before its interruption and had a subsequent accepted present before the guard fired.

| First 55 s | 6 workers | 10 workers | 14 workers |
| --- | ---: | ---: | ---: |
| Accepted presents | 1,440 | 1,442 | 1,445 |
| P99 present interval | 44.84 ms | 36.87 ms | 33.80 ms |
| Longest gap | 10.31 s | 10.31 s | 10.34 s |
| Time in gaps over 100 ms | 31.10 s | 31.15 s | 31.07 s |
| Compute waits without a result | 9 | 12 | 11 |

Over the first 75 s, six and ten workers accepted 1,454 and 1,463 presents and spent 50.87 and 50.54 s in gaps over 100 ms, respectively. P99 was 124.87 and 186.52 ms, while the longest gaps were 10.66 and 10.49 s. Both characters' facial skin was visible in the same opening dialogue shot on six and ten workers. The comparable prefixes give little reason to change the worker count. A complete run and a saved indoor rendering check remain pending.

On the ten-worker release, the first two complete long gaps lasted 10.31 and 10.14 s. Logged compute waits overlapped 9.72 and 10.10 s of those gaps, respectively, with no logged screen waits overlapping either. The follow-up changed only the compute wait from 10 s to 2 s on the same build. It kept the 3 KiB cutoff and ten general workers. A separate build ended the 2 s launch at 102.05 s. Over the first 75 s, the shorter wait reduced the first long gap from 10.31 to 3.11 s. Two later gaps lasted 10.51 and 12.07 s and overlapped 10.49 and 10.00 s of logged screen pipeline waits, respectively.

| First 75 s | 10 s compute wait | 2 s compute wait |
| --- | ---: | ---: |
| Accepted presents | 1,463 | 1,471 |
| P99 present interval | 186.52 ms | 276.78 ms |
| Longest gap | 10.49 s | 12.07 s |
| Time in gaps over 100 ms | 50.54 s | 50.50 s |
| Compute waits without a result | 25 | 52 |

The shorter compute wait left about the same total time in gaps over 100 ms. The private capture showed character skin earlier in the scene, and the run ended before the matching face close-up. This prefix leaves the rendering comparison and full cold score open. For the two longest screen waits in the 2 s arm, 10.489 and 10.000 s of overlap were before the last shader translation was logged. Less than 3 ms was after it. That interval includes time waiting for a worker, so it cannot establish how much time the translator spent working.

The indexed CPU profile also sampled register renaming and live-out lookup. An independent source experiment reuses a predecessor's live-out values when the incoming register set matches. It also keys the existing sorted live-out lists by numeric register index. Eight alternating native passes matched all 254 DXIL and host metadata outputs and both translation errors in a stratified 256-input sample. Median summed translation time was 2.558 s on the control and 2.504 s on the experiment. A second sample used the 18 stages selected from the most overlapping wait groups in the longest complete gaps of two earlier traces. All 18 outputs matched across eight passes. Median summed time was 5.025 and 5.006 s, respectively. The native translator suite passed 211 tests with two ignored. The targeted sample showed little change in translation time. [Experimental source](https://github.com/UwUCammie/VIctory-7900XTX/commit/a9912f37)

### Reusing work across shader optimizer passes

An independent experiment keeps the dominator tree until a branch is pruned and compacts each block's instructions in place. Eight alternating native passes on 256 stratified inputs matched all 254 translations and both translation errors. Median summed translation time was 2.477 s for the control and 2.488 s for the experiment. All 18 shaders selected from earlier long gaps matched across eight passes, with summed medians of 4.992 s and 4.990 s, respectively. The native shader suite passed 211 tests with two ignored. The targeted sample showed no meaningful reduction in translation time. [Experiment source](https://github.com/UwUCammie/VIctory-7900XTX/commit/d99038da)

### Half-precision views in fresh descriptor tables

The Wine branch's per-list cache could copy the title's original typed buffer descriptor before the renderer applied the unsigned format needed for half-precision bit moves. The fix sends those slots through the existing conversion. The generated fresh-table regression checks the actual host descriptor in the slot past the start of the declared range. On an RX 7900 XT with Wine 11.22, RADV 26.3.1 and vkd3d-proton `71cae091b06571e`, the unpatched build failed with the list cache enabled. The fix passed with the cache enabled. Both builds passed with it disabled, and each test executable matched 112 source checksums. The cold gameplay comparison applies only the runtime fix to the 3 KiB build and uses the same launch and dialogue route. [Wine PR #14](https://github.com/borntofrag34/VIctory-7900XTX/pull/14)

The matched gameplay run included the same opening dialogue close-up. Both characters had visible skin on the control and the patched build in that shot. The patched launch yielded to another build at 90.66 s, so a full cold score and the reported mouth and indoor rendering issues remain open. In the verified first 75 s, the two builds accepted 1,463 and 1,450 presents and spent 50.54 and 50.87 s in gaps above 100 ms. The patched run's 20.06 s longest gap overlapped 19.75 s of logged screen pipeline waits, including 19.74 s before the last shader translation was logged. The 10 s compute-budget diagnostic uses opt-in queue timing to separate queue residence from translation. Its first launch yielded at 13.19 s, before the opening stalls. The one screen group overlapping the longest gap for at least 0.5 s contained two stages. The sum of their median translation times was 2.88 ms across five serial native passes using the runtime's translator features. The native probe excludes queueing and driver work. The paired diagnostic will measure the same trace with requests that already have a waiting caller given priority.

A repeat of the original control accepted 1,462 presents and spent 50.53 s in gaps above 100 ms over the same first 75 s. Its longest gap was 11.07 s. The executable, driver files, input and profile matched the first control. A separate build interrupted the repeat at 146.28 s. The three prefixes leave full-run performance of the half-view fix open.

### Legacy save migration under Wine

A temporary fixture on the current Wine branch reproduced deletion of a legacy save directory when one blob could not be read. After towiice's fix, migration kept the original directory and committed no partial version. Once the simulated bad entry was repaired, migration succeeded and both blob contents matched. The regression plus ten other save tests passed in the Windows MSVC test executable under Wine 11.22. The existing NTFS hard-link-limit test failed on Btrfs. Both executables matched 163 runtime source checksums. [Wine PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/13)

### Reusing command lists at thin replay construction

Ported the upstream constructor reuse patch to the Wine tree for a comparison on the same binary. Both arms keep the existing completed-list pool enabled. Only the constructor lookup differs, and the runtime must report its active setting. A generated D3D12 fixture for the two arms checks whether construction acquires a previously completed list and submits it again. The two fixture cases passed on the RX 7900 XT with RADV 26.3.1, Wine 11.22 and vkd3d-proton `71cae091b06571e`. The Windows MSVC executable and PDB matched 108 source checksums. Reuse on took the exact completed list. Reuse off left it in the pool. Thin placeholders left it alone in both cases. The release verified 171 source checksums. The independent Wine PR branch also passed both fixture settings with 111 verified source checksums. Both full trials are pending. [Upstream PR](https://github.com/avatarmanz/VIctory-7900XTX/pull/457), [Wine PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/7), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/f5f3c6cb)

### Wine physical page remapping

With the split Wine page table, a request for a different valid first page and a freed second page left the second original page reserved. The preflight port resolves and retains all requested pages before updating the destination. The unchanged-content test reproduced the failure on the original code. That test and the existing alias/unmap test both passed on Wine 11.22 with the mapped pages feature enabled. No GPU or game files were used in these tests. An independent watch-state port passed two tests covering cleanup of stale mappings and sibling views. [Remap preflight PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/6), [Watch-state PR](https://github.com/borntofrag34/VIctory-7900XTX/pull/5)

### Null constant-buffer descriptors

Adapted the stale-slot fix from fxceless #304 to the Wine build. The Windows MSVC tests verified that null writes replace an existing descriptor in both title record formats. The RX 7900 XT test under Wine 11.22 and vkd3d-proton `71cae091b06571e` also replaced live host views with typed null views, cleared their raw twins, and confirmed that the device remained available. The executable and PDB matched 108 runtime source checksums. [Upstream fix](https://github.com/fxceless/victory-fork/pull/304), [Wine test source](https://github.com/UwUCammie/VIctory-7900XTX/commit/0989cf16)

The three checks passed again on the exact Avatar main-based PR head `82313d59`, with 111 source checksums and confirmation that the raw twins were active on the physical device. [Avatar PR #446](https://github.com/avatarmanz/VIctory-7900XTX/pull/446)
