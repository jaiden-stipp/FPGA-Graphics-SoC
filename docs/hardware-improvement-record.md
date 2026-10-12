# Hardware improvement and measurement record

## STA-001: fitted timing analysis, October 10, 2026

Baseline source/report revision `ba78b16`; existing IntegerMulSoC bitstream unchanged.
Fresh TimeQuest queries of the fitted database confirm +0.468 ns worst setup
(half-cycle local RAM â†’ UDP loader), +1.032 ns CPU endpoint setup
(forwarding/MUL/next-PC), +1.456 ns GPU endpoint setup (fan-area/culling),
+4.901 ns cache endpoint setup, and +0.115 ns worst hold (Ethernet RX FIFO input).
The original multicorner report passes its reported checks with no unconstrained
paths in its coverage summary. CLOCK_50 restricted Fmax 52.45 MHz is a static
estimate, not a measured operating frequency. No hardware optimization, new board
test or performance gain is claimed. Detailed conclusions and limits:
`docs/static-timing-analysis.md`; raw reports and hashes:
`docs/benchmarks/static-timing-001/`.

Started October 9, 2026. This is the reference for hardware experiments and
evidence-backed resume claims. No hardware optimization has been implemented or
measured as part of starting this record.

## Evidence rules

- Label every number as measured, calculated from measurements, a design
  configuration, or an estimate. Estimates are not results.
- Keep raw reports in `docs/benchmarks/`, alongside the method and workload.
  Do not rely solely on ignored files in `build/`.
- Record baseline and candidate Git revisions, dirty changes, firmware/package
  hashes, programmed bitstream hash, board, clock frequencies, tool versions,
  and commands. Hashes must describe the artifacts actually tested.
- Compare the same scene, camera, input sequence, assets and software unless
  explicitly testing a combined change. Separate cold and warmed-cache runs.
- Record sample counts, durations and individual repeated runs. Report variation
  and failures; do not select only the fastest run.
- Distinguish simulation from physical-board measurements, and timing-analysis
  limits from an actual operating clock. CPU and GPU times overlap; do not add
  them to invent a frame time.
- Derive FPS from completed-frame differences and elapsed sampling time.
  Counter-based frame times must state the counter clock and sampling semantics.
- Report absolute before/after values with any percentage or speedup.
  Time reduction = `(baseline - candidate) / baseline * 100`;
  throughput increase = `(candidate - baseline) / baseline * 100`.
- Verify rendering, collision, loader readback and cache correctness before
  presenting a speed result as a working improvement. Record resource usage and
  timing slack from actual Quartus reports when available.
- A result is scoped to its tested workload. Do not generalize a standing scene
  to a complete game or claim implementation of features that remain incomplete.

## Historical software measurements: context only

These are earlier physical-board observations from the castle grounds standing
view, before the wider camera and palette update. They are software changes on
the existing hardware, not evidence of a hardware optimization. The earlier
checkpoint documented a 50 MHz counter clock. Milliseconds below are calculated
as `cycles / 50,000`. Counters represent individual published frame snapshots,
not repeated-run averages.

| Earlier checkpoint | Frame cycles, measured | Frame ms, calculated | CPU cycles, measured | CPU ms, calculated | Evidence |
|---|---:|---:|---:|---:|---|
| Initial foundation | 5,005,212 | 100.10424 | 4,212,564 | 84.25128 | [Raw report](benchmarks/historical-castle/physical-foundation.json) |
| Frustum/CRC changes | 3,336,709 | 66.73418 | 2,632,611 | 52.65222 | [Raw report](benchmarks/historical-castle/physical-optimized.json) |
| Vertex reuse and floor events | 2,502,504 | 50.05008 | 1,790,552 | 35.81104 | [Raw report](benchmarks/historical-castle/physical-vertex-reuse.json) |

The vertex-reuse report also records 35 completed frames over 1.766 seconds:
`35 / 1.766 = approximately 19.82 FPS`. This is a short host-side sample,
not a sustained-game average. Other globals in its held-CPU snapshot may belong
to a partially executed next frame. Original tested Git revisions and artifact
hashes are not captured in these raw reports; the current package must not be
treated as the old tested package simply because its filename matches.
Use these observations as historical context, not a controlled hardware A/B
benchmark or an unqualified resume performance claim.

## Hardware experiments

No physical-board hardware improvement has been measured yet. A fresh baseline
is required for the current camera, firmware and bitstream before claiming an
on-board improvement.

The first implementation uses a 4 KiB direct-mapped cache with 32-byte lines;
this is a design configuration, not a measured optimal size. The
earlier 40%-stall / 75%-removed / 1.43x example was hypothetical arithmetic,
not a measurement of this system. No cache FPS prediction is established.

For the cache experiment, collect SDRAM request counts, CPU external-memory
stall cycles, cache hits/misses and fill cycles with precisely documented counter
definitions. Measure stationary, moving-camera and area-transition workloads.
Record BRAM, logic usage, timing slack and functional results as well as speed.

### CACHE-001: blocking SDRAM data cache, October 9, 2026

Implemented at the bridge/controller boundary. Write-through stores, byte masks,
no write allocation, loader bypass and invalidation; eight single-word reads
per line fill. The controller, original CPU/GPU sources and game data are
unchanged. [Architecture and reproduction commands](sdram-cache.md).

Measured using ModelSim Intel FPGA Edition 10.5b and the production SDRAM
controller/device model, with the same memory test and `CACHE_ENABLED` parameter
set to 0 or 1. The configured clock period is 20 ns. Each result is one
deterministic access sample, not an average or physical-board measurement.

| Access | Uncached simulation cycles | Cached simulation cycles |
|---|---:|---:|
| First read of the tested line | 13 | 107 |
| Immediate repeated read | 13 | 3 |

The repeated access uses 10 fewer cycles (calculated reduction: `10/13 * 100`,
approximately 76.9%). The cold access uses 94 more cycles because it fills eight
words before completing. These results demonstrate the hit/miss tradeoff; they
do not establish better game performance. Refresh phase and workload affect
latency. The standalone synthetic-memory test also measured 41 versus 1 wait
cycles, using a different model and counting boundary; do not mix it with the
controller/device results.

Functional evidence:

- [Cache unit log](benchmarks/cache-001/cache-unit.log.txt): fills, hits, conflicts,
  byte-masked write-through, no write allocation, loader bypass, in-flight
  invalidation and 128 deterministic mixed-address write/read pairs.
- [Cached controller/device log](benchmarks/cache-001/memory-cached.log.txt) and
  [uncached comparison](benchmarks/cache-001/memory-uncached.log.txt): subword
  loads/stores, sign extension, address lines, alignment and refresh.
- [Real CPU pipeline log](benchmarks/cache-001/cpu-pipeline.log.txt): self-test
  passed with 5,892 pipeline wait cycles and no duplicate retirement using the
  final RAM coding pattern and diagnostic wiring.
- [Ethernet loader log](benchmarks/cache-001/udp-loader.log.txt),
  [MMIO log](benchmarks/cache-001/mmio.log.txt), and
  [local-memory log](benchmarks/cache-001/local-memory.log.txt): passed.
- [Measurement manifest](benchmarks/cache-001/measurements.json): source hashes,
  fixture hash, base Git commit and preserved FPGA image hash.

The first MMIO regression needed its wildcard port connection updated for the
new diagnostics. An uncached comparison initially encountered a stale ModelSim
library after a partial recompile; compiling all short tests together resolved
it. The archived logs above are the passing runs.

The first synthesis attempt mapped the data array into registers rather than
block RAM and reported 84,802 estimated logic elements. That candidate was
rejected and its fit stopped deliberately; the
[rejected synthesis summary](benchmarks/cache-001/rejected-register-array.map.summary.txt)
is retained. The data-array coding pattern was corrected to a single
byte-enabled write port and synchronous read, then functional verification and
synthesis were rerun. This correction is not a game-performance result.

Quartus Prime Lite 18.1.0 Build 625 completed synthesis, fitting, timing analysis
and assembly for the separate `CacheSoC` candidate on EP4CE115F29C7:

| Reported candidate property | Value | Evidence |
|---|---:|---|
| Fitted logic elements, whole SoC | 20,833 / 114,480 | [Fitter summary](benchmarks/cache-001/cache.fit.summary.txt) |
| Fitted memory bits, whole SoC | 2,659,668 / 3,981,312 | [Fitter summary](benchmarks/cache-001/cache.fit.summary.txt) |
| Lowest reported timing slack across summary checks | +0.110 ns | [Timing summary](benchmarks/cache-001/cache.sta.summary.txt) |
| Cache data RAM | Four 1024 x 8 arrays, 32,768 bits total | [RAM inference rows](benchmarks/cache-001/cache-ram-inference.txt) |
| Cache tag RAM | 128 x 15 array, 1,920 bits | [RAM inference rows](benchmarks/cache-001/cache-ram-inference.txt) |

The 50 MHz main clock constraint and other reported constraints passed using
the existing SDC. This is static timing analysis, not a measured maximum clock
frequency or a physical-board functional pass. Resource counts are whole-design
values, not isolated cache overhead; no matched uncached rebuild resource
comparison is claimed. Tool warnings remain in the archived
[map](benchmarks/cache-001/quartus-map.log.txt),
[fit](benchmarks/cache-001/quartus-fit.log.txt),
[timing](benchmarks/cache-001/quartus-sta.log.txt) and
[assembly](benchmarks/cache-001/quartus-asm.log.txt) logs.

Candidate file: `build/quartus-cache/CacheSoC.sof`, SHA-256
`BC0948F73F1FF97F71D36411EB62E376D485D9559D8D6AA46D0F9D84CD596927`.
The original `build/quartus/SoC.sof` remains unchanged with SHA-256
`B89797F51864CF1AA39E7C7835AD7105FB4D2A689986EED8F624CD8F70318617`.
No cache-enabled image has been programmed onto the board. Game FPS, sustained
hit rate and physical performance remain unmeasured.

### Entry template

- Experiment ID and date:
- Change and hypothesis:
- Status: proposed / simulated / measured on board / rejected:
- Baseline and candidate source revisions, including dirty changes:
- Firmware, assets and bitstream SHA-256 for both cases:
- Board, clocks, tools and relevant configurations:
- Workload, camera, input replay and cold/warm conditions:
- Reproduction commands and raw evidence links:
- Counter definitions, warm-up, sample count and duration:
- Individual results and variation:
- Absolute before/after values and derived improvement formulas:
- Functional validation and failures:
- Quartus resource usage and timing results:
- Tradeoffs, limitations and supported conclusion:
- Resume wording supported by this evidence, or why none is supported yet:

## Resume claim status

[GPU-001](projection-precision.md) records a confirmed simulated projection
precision defect and its correction. Its measured pixel error is a correctness
metric; no game performance improvement or physical gameplay acceptance is
implied.

Movement-dependent terrain correctness investigation is recorded separately in
[TERRAIN-001](terrain-loading-diagnosis.md). Physical CPU reads passed the
recorded cache integrity workload, but gameplay correctness and the direct
terrain comparison remain unresolved. This is diagnostic evidence, not a
measured cache performance improvement.

[BURST-001](burst-cache-fills.md) now supports a physical memory-microbenchmark
claim: median cycles for 64 cold-line reads fell from 7,239 to 1,539 (78.74%)
across three runs per image on the 50 MHz DE2-115. The conflict workload fell
from 57,335 to 11,794 cycles (79.43%); warm reads stayed at 4,098 cycles.
Integrity checks passed. The accepted build adds 61 logic elements with unchanged
RAM/DSP/PLL counts and passes reported timing constraints. The first candidate
failed physical data integrity and was corrected; its evidence is retained.
Gameplay rendering/collision acceptance and FPS comparison remain separate.

Claims should name the FPGA platform, tested workload, before/after result and
method. Example structure, with no invented values:

> Implemented [change] on [platform], reducing [metric] from [measured baseline]
> to [measured candidate] on [workload], verified using [method].

Keep the experiment ID and evidence links with the claim for interview review.

[DEPTH-001](depth-banding-diagnosis.md) reproduces camera-dependent striping in
the actual rasterizer: an identical triangle with cyclic vertex order wrongly
overwrites 8,690 pixels due to rounded depth slopes and anchor-dependent depth.
This is diagnostic simulation evidence. No hardware correction or performance
improvement is claimed.

[COLLISION-001](floor-penetration-correction.md) records a software correctness
fix for horizontal movement through rising floor planes. Its native castle-data
fixture detects 207 penetrations before the correction and zero afterward.
This is a bounded correctness result, not hardware performance evidence.
The attempted board load failed before uploading; traversal acceptance is pending.

Currently supported implementation wording:

> Designed and verified a 4 KiB write-through SDRAM data cache for an RV32I FPGA
> SoC, including byte-masked stores and Ethernet-loader invalidation; passed CPU
> and memory simulations and Quartus fitting/timing checks on Cyclone IV E.

A latency claim must explicitly say simulation and name the repeated-read
fixture; it must also retain the cold-miss limitation. No game FPS claim is
supported by CACHE-001.

## CACHE-LINES-001: equal-capacity line-size comparison

Measured October 10, 2026: tested 8-, 16- and 32-byte lines at 4 KiB data capacity on the physical DE2-115, with one identical RV32I probe and castle asset package, three trials per image. Retained 32-byte lines: 16-byte lines slightly improve floor-query time but slow mesh-data traversal; 8-byte lines lose both castle kernels while improving a sparse control. All data checksums/readback and timing checks pass. Standing Mario remains approximately 20 FPS; no traversal-FPS gain is established.

See [full comparison and evidence](cache-line-comparison.md) for absolute cycles, miss/fill traffic, every trial, resource/timing reports, source/artifact hashes, workload coverage and limitations. The source baseline and experimental implementation are separate commits.

## CPU-PROFILE-001: physical stall breakdown and submission experiment

Measured October 10, 2026, three trials per configuration on the DE2-115. Added physical retirement, memory-freeze, dependency-bubble and redirect counters with atomic frame snapshots. Standing render records 1,655,341 active cycles, 1,276,552 retired instructions, 43,886 memory freezes and 27,421 dependency bubbles; render memory freezes are a calculated 2.651%. No FIFO-capacity waiting was observed in the captured standing/movement frames. An optional software FIFO-reservation prototype reduces measured standing command time from 294,210 to 270,282 cycles (-8.133%) on identical hardware, while FPS remains approximately 20, including a separate uninstrumented batching control. This is a software submission result, not a hardware speedup. Instrumentation costs +585 fitted logic elements with unchanged RAM/DSP/PLL counts and passing timing. Original FPGA and Mario were restored.

See [counter contract, full results and reassessment](cpu-profiling.md) and [raw evidence](benchmarks/cpu-profile-001/measurements.json). Baseline 7280023, instrumentation/prototype 02d08ab, corrected measurement harness b388364. Next priority is function-level profiling of CPU transforms, clipping and pose arithmetic; larger FIFO, DMA and superscalar changes are not justified by these measurements.

## RENDER-PROFILE-001: individual transform, clipping and animation costs

Measured October 10, 2026, with three physical trials each for standing control, standing detail and moving detail, using the existing counter image and unchanged game assets. Standing detailed render medians: terrain vertex transforms/outcodes 732,782 cycles (14.65564 ms), triangle classification/clipping 297,742 cycles (5.95484 ms), animation joints 109,392 cycles (2.18784 ms), and vertex posing 160,161 cycles (3.20322 ms). Timers include instrumentation; these are not pure arithmetic costs. Matched frame 167 has +24,219 net render cycles from detail profiling and identical seven GPU raster-event counts. FPS stays approximately 20; no optimization or hardware speedup is claimed. Disabled profiling preserves the original CPU and assets byte-for-byte, and the original FPGA/game were restored.

Baseline `3ac198d`, implementation `9ead800`. See [full scope definitions, overhead and next-step assessment](render-function-profiling.md) and [raw evidence/hashes](benchmarks/render-profile-001/measurements.json). Integer low-32-bit MUL is the strongest general CPU candidate; validate resident GPU terrain precision and replace repeated per-vertex admission checks before expecting offload savings. Multiplication's individual share, resource cost and speedup remain unmeasured. GPU skeletal posing needs a new joint interface; one matrix per current mesh cannot substitute for it.

## MUL-001: single-cycle integer MUL and measured game improvement

Implemented and measured October 10, 2026. Added MUL-only decode/EX arithmetic with existing forwarding/writeback, guarded optional `fixed_mul` firmware and a permanent emitted-instruction audit. Real-pipeline tests pass for 134 operand pairs, hazards, branch flushing and memory freezes; three physical 256-pair probes agree with an independent Python checksum. Original game assets remain identical.

On the physical FPGA, three trials each of an original-idle-pose castle fixture reduce CPU render from 1,678,270 to 945,783 cycles (33.56540 to 18.91566 ms at configured 50 MHz), a calculated 43.645% reduction with identical command counts and seven GPU raster-event counts. Normal animated standing gameplay measures approximately 20 to 30 FPS; an unprofiled MUL control also measures approximately 30. Moving diagnostics do not establish an identical-route speedup. Whole-SoC cost versus counter-enabled baseline: +76 logic elements, +6 embedded 9-bit multiplier elements, unchanged memory/PLLs. All reported timing passes; CLOCK_50 setup slack 0.468 ns. No maximum-frequency, power or complete-game claim is supported.

Baseline `af8580f`, RTL `8aa373b`, opcode audit `122bed3`, arithmetic probe `cdf0f8c`, controlled-pose fixture `762895b`. [Full implementation/results](integer-mul.md) and [raw evidence](benchmarks/integer-mul-001/measurements.json) preserve exact scope, hashes and reproduction. Accepted MUL FPGA and normal animated unprofiled Mario are loaded; prior baseline artifacts remain available.

## POST-MUL-REVIEW-001: remaining bottlenecks

Measured October 10, 2026 at source baseline `3f55435`, three fresh physical standing and three movement trials. Standing CPU render is 18.91746 ms: transforms/outcodes 6.34360 ms, command submission 5.88420 ms, classification/clipping 4.04662 ms. Moving render median is 21.26326 ms with command submission 7.71204 ms. Render memory freezes remain approximately 0.90 ms, with no observed FIFO capacity wait. FPS stays approximately 30 under current simulation/presentation cadence. GPU total includes command gaps and VGA swap waits; overlapping counters are not serial costs. No new optimization, speedup or correctness fix is claimed. Normal unprofiled MUL Mario is restored.

[Assessment and prioritized experiments](post-mul-bottlenecks.md) and [raw evidence/hashes](benchmarks/post-mul-review-001/measurements.json) preserve measured scopes. Prioritize safe terrain GPU offload and finer command-submission profiling, then isolated clipping fractions and GPU drain timing; cache redesign and superscalar execution remain secondary in these views.

## TERRAIN-OFFLOAD-001: conservative terrain admission and finer profiles

Implemented October 10, 2026, baseline `6b8a298`, implementation `3cec385`, using unchanged MUL hardware. Added bounds/rounding admission with direct fallback, saved matrices, initial source-bounds validation, and an optional atomic fine ABI for CRC/check/write and clipping fraction/intersection spans. Five admission/fallback tests plus 29 world/collision/CRC and 13 portable tests pass.

Twenty-seven physical trials cover controlled original-pose castle views and an authored admitted-terrain fixture. The eligible 210-triangle fixture reduces CPU render from 365,114 to 9,083 cycles (7.30228 to 0.18166 ms at 50 MHz), a calculated 97.512% reduction, with matching seven GPU event counts. Both remain about 30 FPS under current cadence. Castle snapshots admit zero chunks and preserve fallback geometry; no castle offload/FPS improvement is claimed. Standing fine diagnostics measure 6,527 CRC updates, 7,011 checks/writes and 290 intersections; fine timers add significant overhead and remain optional. No new RTL, fitted resource or frequency change is claimed. Normal unprofiled direct MUL Mario is restored.

[Full explanation, scope and results](terrain-offload-and-profiling.md) and [raw evidence/hashes](benchmarks/terrain-offload-001/measurements.json). Next work must address spatial chunk bounds and exact fractional translation before expecting castle offload; a simple 32-bit shifted-numerator divider substitution is not proven safe.


## SCREEN-EDGES-001: bounded rendering correctness corrections

Measured October 10, 2026 against source baseline `c3df05d`. Reproduced a CPU clipping precision fault in an authored large crossing triangle and one valid GPU pixel rejected by depth-gradient rounding. Sixteen-bit clipping fractions with overflow-safe interpolation remove the lost edge probes; generated GPU depth clamping restores 2,802/2,802 covered pixels against a cleared buffer. Three native clipping tests, three GPU regressions, 47 existing host tests, firmware subset/instruction checks and Quartus fitting/timing pass. Sampled original castle geometry at 680 constructed poses has zero missing edge probes before and after; the user's large-region visual fault remains unconfirmed.

Three physical standing animated trials per image at 50 MHz: median CPU render rises from 18.91756 to 19.14806 ms (+1.218%), clipping scope rises 14.204%, and FPS remains approximately 30. Combined correctness change costs +114 fitted logic elements with unchanged RAM, multipliers and PLLs. Worst setup slack is +0.365 ns; worst hold slack is +0.091 ns. These are bounded correctness results and measured cost, not a performance improvement or complete-game rendering claim. Explicitly programmed baseline and candidate bitstream hashes, all trials, failed unknown-image attempt and final running-game check are preserved. Normal unprofiled corrected Mario is loaded.

[Implementation, scope, reproduction and remaining acceptance](screen-edge-rendering.md) and [raw evidence](benchmarks/screen-edges-001/measurements.json).


## ARCH-UPGRADE-001: replay foundation and optional terrain extension

[Stage 0/1 results](architecture-stage-0-1.md) preserve the implemented deterministic terrain/controller/camera replay, complete color/depth captures, generic static Quake repeat and backwards-compatible fractional mesh command. Seven castle frames match all 1,573 ordered submitted triangles and all terrain pixels. Actor/transition and physical full-frame acceptance remain pending. Fifty-six host tests and relevant RTL, firmware and timing checks pass.

At 50 MHz, three physical standing trials per configuration measure median CPU render 19.14806 ms baseline, 21.57750 ms cell-packed direct, 23.05500 ms cell-packed fractional GPU and 21.62288 ms minimum-32-face fractional packing. Both layouts regress and are not promoted; no FPS improvement is claimed. The candidate adds 779 logic elements with unchanged memory/multipliers/PLLs, +0.364 ns worst setup and +0.088 ns worst hold. The first fit failed setup by 0.250 ns and was never programmed; a product register adds nine cycles per resident triangle. Original image and unprofiled Mario are restored and advancing frames. [All trials and scope](benchmarks/arch-upgrade-001-stage-1/measurements.json) and [hashes/build/capture evidence](benchmarks/arch-upgrade-001-stage-1/manifest.json) support an implementation/validation claim, not a performance improvement. Stage 1's next decision is cheaper selection/admission and useful residency; later stages remain unstarted.

## GPU-PACKED-001: ARCH-UPGRADE-001 Stage 2A

Implemented/measured October 11, 2026, baseline `460957e`, implementation `2f226d6`. Added backward-compatible atomic one-to-four-byte MMIO enqueue through four banks of the existing 256-byte FIFO, exact CRC/tail serialization, conservative reservations and read-only loader STATUS capabilities. Original models, collision, gameplay, packing and clocks are unchanged. Fifty-nine host tests plus relevant RTL/audits pass; seven castle terrain frames, two Quake static views and eight authored fixtures match full color/depth/palette and ordered triangles. Full actors/transitions/physical framebuffer coverage is not claimed.

On one final image at 50 MHz, three standing detailed trials reduce median command cycles 281,882 to 230,481 (-18.235%) and render cycles 957,403 to 905,765 (-5.394%). Fine checks/writes fall from 7,011 to 1,872 invocations (-73.299%); CRC still updates 6,527 bytes. Instrumentation materially affects those spans. Three ordinary uninstrumented trials reduce the existing **update-plus-render live timer** from 913,166 to 905,274 cycles (18.26332 to 18.10548 ms, **-0.864%**); these values are non-atomic and support no render-only/full-game FPS claim. FPS remains approximately 30. Three moving diagnostics show no startup/submission failure or FIFO-capacity wait, without a matched movement-performance baseline.

The final image costs +142 fitted logic elements, +16 logical memory bits and +3 M9Ks versus the Stage 1 candidate; multipliers/PLLs are unchanged. Worst multicorner setup/hold are +0.182/+0.126 ns at unchanged clocks. Combined optional Stage 1/2A cost versus ScreenEdges is +921 logic elements; do not attribute the entire difference to packing. Normal unprofiled packed Mario is loaded with readback and advancing frames (56 to 86); prior accepted image/package hashes are preserved. DMA is deferred pending staging economics, ownership and arbitration design.

[Full results, scope and deployment](architecture-stage-2a.md), [raw trials/resources](benchmarks/arch-upgrade-001-stage-2a/measurements.json), [hashes and reproducible evidence](benchmarks/arch-upgrade-001-stage-2a/manifest.json). Defensible resume wording: “Implemented and verified atomic packed GPU command submission on an FPGA SoC, reducing sampled per-frame MMIO stores 73.3%; measured a 0.86% reduction in ordinary standing-view CPU update/render time and documented instrumentation, timing and memory-banking costs.” No game-FPS gain is supported.


## GPU-DMA-001: ARCH-UPGRADE-001 Stage 2B (not promoted)

Measured October 11, 2026. Baseline/staging commit df9c539; read-only SDRAM DMA, arbitration, bounds, exact FIFO publication and loader cancellation implemented in 59a4d3a; command-local staging correction in 40e4ee1. Generic transport preserves models, collision, gameplay, camera, CRC and clocks. Staging-only trials showed 20.6-34.5% less CPU time for larger saved streams, excluding DMA and GPU drain; that is not a game-speedup result.

On one timing-passing candidate image at 50 MHz, three ordinary standing trials per firmware measure median update-plus-render 905,274 cycles packed, 986,750 global-state DMA and 982,405 command-local DMA. Final DMA regresses **8.520%** (18.10548 to 19.64810 ms); FPS stays near 30. The software correction saves 4,345 cycles versus the unsuccessful first DMA driver, but is not an improvement against packed. Three detailed trials per firmware separately expose additional retirement/freezes, with small DMA grant/FIFO waits; instrumentation, buffer ownership checks and overlapping spans are documented. All eighteen physical trials and both driver versions are preserved.

Final hardware costs +1,113 logic elements and +4 logical memory bits versus Stage 2A; M9K count 354, physical memory implementation bits, 80 multiplier elements and two PLLs are unchanged. Worst setup/hold slack +0.401/+0.086 ns at unchanged clocks, with no unconstrained setup/hold paths. The initial fit failed setup by 0.507 ns and was never assembled/programmed; registered descriptor validation resolves the half-cycle path. Twenty-three host tests, nine affected RTL regressions plus maximum descriptor-tail coverage, firmware audits and exact seven-castle/two-Quake/eight-fixture replays pass. Full actors/transitions/physical framebuffer/traversal acceptance is not claimed.

DMA is an experimental optional backend, not the selected transport. Exact accepted Stage 2A image and normal packed Mario are restored, all upload/readback verified, with final frame progress 2 to 32 over the one-second check. [Results, interpretation and reproducible commands](architecture-stage-2b.md), [all measurements](benchmarks/arch-upgrade-001-stage-2b/measurements.json), [hashes/raw evidence](benchmarks/arch-upgrade-001-stage-2b/manifest.json). Defensible resume claim: designed and verified a reusable SDRAM command DMA backend with arbitration/cancellation, and rejected default deployment after measured regression. No positive DMA performance, power, Fmax or complete-game claim is supported.


## GPU-SETUP-001 / ARCH-UPGRADE-001 Stage 3: overlapping setup and rasterization

Implemented and measured October 11, 2026. Baseline 6153efa; initial implementation
2bf56dd; Quartus compatibility correction 8bb928c. A selectable producer computes
setup/depth gradients while an ordered consumer rasterizes, with a stable two-record
queue and explicit busy/drain page-swap barrier. Existing arithmetic, strict depth
order, command ABI, models, gameplay, cache and clocks are preserved.

Seventeen complete captured terrain/fixture frames (seven castle, two Quake, eight
authored) match accepted color, depth, palette and ordered triangle references
exactly. Eleven affected RTL regressions and six existing host tests pass; reset
with queued/active work and full-queue stability are covered. Eighteen physical
trials cover serial and overlap images, resident-mesh GPU probes, ordinary standing
Mario and instrumented standing diagnostics. The measurement probe passes C-subset
and a 580-instruction RV32I audit. Coverage excludes whole-game actors/transitions,
physical framebuffer capture and full-level traversal acceptance.

A synthetic 128-face resident mesh with 33x33 projected bounds reduces GPU total
minus swap wait from 221,644 to 216,820 cycles (4.43288 to 4.33640 ms at 50 MHz,
2.17646% less work before swap waiting). The 65x65 case saves the same 4,824 cycles;
the 5x5 case adds two such cycles and 256 raster-busy cycles. These are synthetic
GPU scheduling results, not original-game FPS gains. Ordinary standing update+render
median is identical at 905,336 cycles in both images, with FPS near 30. Matched
instrumented frame 251 has identical seven event counts and geometry stalls falling
238,048 to 209,639; nested/overlapping spans are not summed as serial frame time.

Matched-control fitted cost: +1,010 logic elements (22,774 to 23,784), unchanged
2,659,684 logical memory bits, 354 M9Ks, 80 embedded 9-bit multiplier elements and
two PLLs. Candidate worst multicorner setup/hold slack is +0.311/+0.089 ns at
unchanged clocks, with zero unconstrained setup/hold clocks/input/output paths.
No maximum-frequency or power improvement is claimed. Initial tool failures and
both hardware hashes are retained. Serial stays the global fallback; Stage 3 is
accepted as an optional reusable scheduling upgrade. Stage 2B DMA stays disabled.

Resume-safe claim: designed and verified an ordered setup/raster overlap engine,
validated exact output across 17 replay frames and measured 2.176% lower GPU work
before swap waiting in a specified synthetic resident-mesh workload. No ordinary
Mario CPU or FPS improvement is supported. [Full results, contracts and reproduction](architecture-stage-3.md), [measurements](benchmarks/arch-upgrade-001-stage-3/measurements.json)
and [raw evidence/hashes](benchmarks/arch-upgrade-001-stage-3/manifest.json).

## GPU-PIXEL-001: two adjacent pixel lanes and parity-banked RAM

October 11, 2026. ARCH-UPGRADE-001 Stage 4. Baseline 8082afd preserves accepted
Stage 3 commit 0a6434b; implementation b465b03 and compatibility/measurement
integration 721fada. Same 50 MHz CPU/GPU clocks, packed commands, game binaries
and assets; experimental command DMA remains disabled.

The two lanes retain ordered triangles, original signed arithmetic/depth clamp,
strict depth comparison and drain. Parity banks provide independent depth/color
access, explicit depth read/write forwarding and parallel clear. VGA read parity
and validity preserve latency and page ownership. Counters count pixels.

Fifteen affected RTL tests and six host tests pass. Exact color/depth/palette,
submitted triangles and seven event counters match 17 castle/Quake/boundary
replay frames. Real RAM tests include asynchronous display parity and explicit
forwarding. Eighteen physical reset trials cover resident-mesh probes, ordinary
standing Mario and instrumented standing Mario on each image. Raw trials,
source/configuration hashes, timing/resources and failures are archived.

Three identical repeats of the 128-face 65x65 resident-mesh probe reduce work
before swap waiting from 618,228 to 313,588 cycles (49.276% less): 38,400 cycles
saved by parallel clear and 266,240 additional cycles, matching raster-busy
reduction. Clear halves from 76,800 to 38,400 cycles. Tiny-probe savings are
almost entirely clear. Matched instrumented frame 251 retains the same seven
event counts while raster busy falls 272,307 to 142,504 cycles. These activity
spans overlap other work and cannot be summed into serial frame time.

Ordinary standing CPU update/render median is identical at 905,274 cycles;
observed FPS remains near 30. No ordinary CPU, complete-game FPS, power or Fmax
improvement is claimed. Fitted cost against matched control is +396 LEs
(23,789 to 24,185), +12 M9Ks (354 to 366 of 432), unchanged 2,659,684 logical
memory bits, 80 embedded 9-bit multipliers and two PLLs. Worst candidate setup/
hold slack is +0.623/+0.105 ns, with zero unconstrained setup/hold clocks and
input/output paths. Both variants pass the reported timing checks.

Stage 4 is selected as an optional reusable upgrade with normal packed Mario;
single-lane fallback and exact Stage 3 rollback remain available. Full firmware/
assets upload/readback and frame progression passed. Selected SOF hash:
52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235.
This is not full actor/transition or physical framebuffer acceptance.

Resume-safe claim: designed and verified a two-lane ordered FPGA rasterizer with
parity-banked depth/color RAM and explicit hazard forwarding; preserved exact
output across 17 replay frames and measured 49.3% less GPU work before swap
waiting in a specified resident-mesh benchmark, including parallel clear, at
+396 logic elements and +12 M9Ks. No ordinary Mario FPS gain is supported.
[Full results and reproduction](architecture-stage-4.md),
[measurements](benchmarks/arch-upgrade-001-stage-4/measurements.json) and
[raw evidence/hashes](benchmarks/arch-upgrade-001-stage-4/manifest.json).

## CPU-GEOMETRY-001: queued Q8 transform/outcode worker

October 11, 2026. ARCH-UPGRADE-001 Stage 5. Baseline 40219cec preserves Stage 4
commit e0d776c. Implementation b677581 / df0649df; reproducible complete-game
stream/profiling integration 765ecbe. Three parallel signed multipliers compute
the original low-32-bit dot products and six shared frustum outcodes, with
bounded input/result queues, configuration ownership, reset/abort safety and
registered FIFO read responses. CPU owns cached source reads and render scratch
copies; no new SDRAM master or cache-coherency path. Game models, collision,
camera, animation, 16-bit clipping fractions, GPU raster/transport and clocks
remain unchanged. Normal packages retain compatibility; offload is feature gated.

An independent 1,152-vertex oracle and the real CPU/MMIO adapter agree with the
production C transform/plane kernel. Three complete actor/game command streams
match through CPUs/cache/SDRAM, and composed GPU replays match color/depth/palette
and 1,332 submitted triangles. The equivalence fixture uses synthetic decoder
backpressure/immediate presentation acknowledgement and supplies no timing claim.
Physical evidence comprises 15 complete comparative reset trials plus three
exploratory probe resets with their printed timings preserved separately.

Ordinary standing Mario CPU update/render medians fall 905,274 to 648,906 cycles
(28.319% less, 18.10548 to 12.97812 ms at configured 50 MHz). Observed FPS remains
around 30; no uncapped FPS improvement is claimed. Detailed transform/outcode
scope medians fall 312,333 to 54,939 cycles (82.410% less), including configuration,
source reads, input writes, polling and result copies. Matched frame 251 retains
all seven GPU events; worker snapshot 252 is a separate actor pose. Paired
on-chip-data 128-vertex probes repeat 38,039 software versus 5,565 complete-adapter
cycles; these are synthetic costs, not SDRAM game-time savings.

Fitted cost is +2,372 LEs (24,185 to 26,557), +12 embedded 9-bit multiplier
elements (80 to 92), no extra M9Ks (366/432), +4 logical memory bits and no new
PLLs. Candidate setup/hold minima +0.424/+0.128 ns pass at unchanged clocks, with
zero unconstrained setup/hold clock/input/output paths. No power/Fmax gain is
claimed. Stage 5 is selected with normal worker-enabled packed Mario; full
CPU/assets readback and running frame progression pass. Stage 4 rollback remains.

Resume-safe claim: designed and verified a feature-gated queued FPGA geometry
accelerator preserving fixed-point transform/frustum semantics and measured a
28.3% reduction in ordinary standing-scene CPU update/render time, including
transfer overhead, with exact complete-game command/GPU replay validation.
This is not complete-level or physical-framebuffer acceptance.
[Architecture/results](architecture-stage-5.md),
[measurements](benchmarks/arch-upgrade-001-stage-5/measurements.json) and
[raw evidence/hashes](benchmarks/arch-upgrade-001-stage-5/manifest.json).


## CADENCE-001: fixed simulation, independent presentation (Stage 6)

Baseline e50d34f (accepted Stage 5 c4f9387), firmware a854e1e. This is a
firmware/runtime throughput change; 85 preserved RTL/SDC sources and the Stage 5
SOF match exactly. No added FPGA resources, clock change, hardware execution
speedup or power claim. All measured artifacts have a finite SHA manifest.

Three atomic reset trials per mode show standing presentation FPS
[29.862323056002584, 29.96906419202057, 29.96906419202057] versus [59.94971959033439, 60.13147718460324, 59.957586273650264]; medians
29.96906 to 59.95759
(100.065% higher).
Three wall-clock movement trials per mode give medians
29.98270 to 44.28544 FPS.
The latter is a timed-input diagnostic, not a cycle-identical or full-level route.

Simulation retains 1,666,667-cycle ticks at configured 50 MHz, including the
existing catch-up cap. Render submission remains about 12.17 ms in standing
snapshots; tick wait falls from median 754,783 to five cycles. Adjacent frames
can repeat the same pose, so this is presentation throughput without
interpolation or a higher new-state/physics rate. Do not call it a doubled
engine speed or constant 60 FPS across the level.

Five scheduler/capability tests and 30 Castle/world tests pass. Repeated C
renders compare captured payload/matrix bytes exactly across 40 idle/moving
updates and preserve state/pose hashes. Firmware subset and ISA audits pass.
TimeQuest minima: setup +0.424, hold +0.128, recovery +2.996, removal +3.478,
pulse +9.194 ns; zero unconstrained setup/hold clocks and I/O paths. These
checks retain inherited external timing assumptions and do not prove a new
frequency or complete CDC reliability. Twelve final atomic physical trials,
six preliminary trials (non-atomic phases excluded), full readback and selected
running-package verification are recorded.

Resume-safe claim: implemented independent render scheduling and atomic
performance telemetry in an FPGA SoC, measured standing-scene presentation
from 29.97 to 59.96 FPS at unchanged 50 MHz while preserving the fixed
simulation timestep, and documented route-dependent performance and timing.
[Results](architecture-stage-6.md),
[measurements](benchmarks/arch-upgrade-001-stage-6/measurements.json),
[artifact hashes](benchmarks/arch-upgrade-001-stage-6/manifest.json).


## RENDER-001 — correctness and render interpolation (October 12, 2026)

Baseline `15ce91c`, software implementation `8f46e2c`, same accepted 50 MHz
Stage 5 hardware/SOF. Source inspection and a deterministic castle replay
identified transparent tree-shadow decals being rendered as opaque foliage
polygons. The generic compiler now retains unsupported appearance faces but
flags them for deferred drawing. Structural geometry/collision, actor meshes,
clips and warps compare exactly. The adapter retains baked brightness and
adds declared flat face lighting; the runtime canonicalizes shared-edge clipping
and interpolates presentation snapshots at the unchanged simulation tick.

Twelve fresh physical trials (three per version/condition) give standing medians
59.93813 to 59.79302 FPS and timed movement medians 44.85692 to 59.95759 FPS
(33.664% higher). This measures the combined software change and reduced drawn
geometry, not an isolated interpolation or hardware speedup. Wall-clock inputs
are not cycle-identical, and this does not establish full-level 60 FPS. All raw
input packets, sample timestamps and atomic counters are archived. Per-frame
snapshots are not average update costs when some frames have zero updates.

34 world, five interpolation/clipping/source and five scheduler/capability tests
pass; firmware/ISA audits and two full-frame GPU replays pass. All 85 accepted
RTL/SDC hashes match. The unsuccessful 12-bit depth experiment used +251 logic
elements, +307,200 logical memory bits, +40 M9Ks and +8 multiplier elements in
actual Quartus fits; it was never programmed. Q4 depth setup was simulated but
not fitted or programmed. Neither solved the missing alpha/decal semantics.
Sources, raw fit/timing reports and replay captures are preserved separately;
normal hardware generation remains the accepted implementation.

Resume-safe claim: diagnosed a source-to-hardware rendering mismatch in an FPGA
SoC, implemented capability-aware appearance lowering and fixed-timestep render
interpolation while preserving source geometry/collision, and measured a timed
movement diagnostic from 44.86 to 59.96 FPS on unchanged 50 MHz hardware.
[Full results and limits](render-correctness-fixes.md),
[raw measurements](benchmarks/render-correctness-001/measurements.json).


## AUDIT-FIX-001 — pipeline consistency and failure bounds

Baseline audit `625dd74`. Strict package/feature preflight, projection and
collision-arithmetic import guards, profile-driven builds, portable isolated
fixtures, schema conformance and bounded worker failure handling are implemented.
Hardware RTL, selected SOF and all 85 accepted RTL/SDC hashes are unchanged;
no physical benchmark or new fit was performed. The guarded firmware is built
separately and was not loaded. Its CPU binary is 29,176 versus 29,124 bytes
(+52), while asset bytes/hash are identical. These are artifact sizes, not
speed improvements. The 5,000,000-cycle timeout is an authored 100 ms failure
budget at 50 MHz, not measured worker latency. Existing performance/resume
claims retain their original evidence and scope.
[Repair validation](repository-consistency-fixes.md).
