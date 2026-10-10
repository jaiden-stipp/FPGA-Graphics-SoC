# Hardware improvement and measurement record

## STA-001: fitted timing analysis, October 10, 2026

Baseline source/report revision `ba78b16`; existing IntegerMulSoC bitstream unchanged.
Fresh TimeQuest queries of the fitted database confirm +0.468 ns worst setup
(half-cycle local RAM → UDP loader), +1.032 ns CPU endpoint setup
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
