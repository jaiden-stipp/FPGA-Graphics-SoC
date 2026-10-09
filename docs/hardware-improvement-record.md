# Hardware improvement and measurement record

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

No quantified hardware-performance claim is supported yet. After a validated
comparison, wording should name the change, FPGA platform, tested workload,
before/after result and method. Example structure, with no invented values:

> Implemented [change] on [platform], reducing [metric] from [measured baseline]
> to [measured candidate] on [workload], verified using [method].

Keep the experiment ID and evidence links with the claim for interview review.

Currently supported implementation wording:

> Designed and verified a 4 KiB write-through SDRAM data cache for an RV32I FPGA
> SoC, including byte-masked stores and Ethernet-loader invalidation; passed CPU
> and memory simulations and Quartus fitting/timing checks on Cyclone IV E.

A latency claim must explicitly say simulation and name the repeated-read
fixture; it must also retain the cold-miss limitation. No game FPS claim is
supported by CACHE-001.
