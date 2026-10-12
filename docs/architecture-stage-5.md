# ARCH-UPGRADE-001 Stage 5: optional queued geometry worker

Implemented, verified and selected. Ordinary standing Mario CPU update/render
median improves 28.319%; observed FPS remains around 30.

Accepted baseline: `e0d776c` (Stage 4), selected SOF SHA256
`52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235`.
Preserve the Stage 4 image and normal packed Mario package as rollback.

## Selection from measurements

Stage 4 standing-frame detailed trials measure transform/outcode costs of
312,328 / 312,333 / 312,328 cycles, clipping at 231,073 each, and skinning at
35,547 / 35,550 / 35,547. These are instrumented scope costs, not predicted
savings. Choose the transform/outcode worker; do not add a skinning accelerator.
The ordinary Stage 4 CPU median is 905,274 update/render cycles at 50 MHz.

## Contract before hardware changes

An optional worker accepts the existing signed 16-bit local XYZ mesh format,
32-bit origin/reference position and signed 16-bit 3x4 Q8 view matrix. It returns
three signed 32-bit camera coordinates and the six existing frustum bits in
submission order. Preserve low-32-bit MUL/sum semantics, arithmetic right shift
by eight, translations, near 257/far 30000 and the existing screen planes.
Clipping intersections and their 16-bit fraction stay in the CPU unchanged.

The worker uses a separate versioned MMIO page at 0x40000100, bounded four-entry
input/result queues, and descriptors of 1..128 vertices (the current mesh bound).
These queue sizes are design choices, not measured optimum sizes. The CPU streams
cached source vertices and copies returned coordinates/outcodes into its existing
render scratch buffer. The worker has no SDRAM access and no cache-coherency role.
Active descriptors exclusively own configuration; results remain stable under
CPU backpressure. Reset/abort discard all queued work. Completion/credit checks
must prevent stale results, overwrite, partial output and descriptor overflow.

Feature-gated firmware retains the CPU kernel on old hardware. The worker is
independently selectable; Stage 4 raster/transport/clocks/game logic/models remain
unchanged. Physical comparisons must include matrix setup, streaming, polling
and returned-result copies, plus ordinary game time. Do not promote the worker
based on standalone multiply throughput.

Acceptance requires independent arithmetic fixtures, FIFO/reset/config ownership
tests, exact ordered game-stream/frame equivalence, full fit/timing/constraint
checks, package capability gates and at least three matched physical trials.
Archive raw measurements and hashes; restore Stage 4 after experiments. Results and selection follow below; the baseline contract above was committed
before hardware edits.

## Implemented architecture and reproduction

The generic worker performs three parallel signed products per coordinate axis,
registers their low 32 bits, accumulates at the original width, floors by an
arithmetic shift of eight, adds translation, and evaluates the existing planes.
Input/result FIFOs preserve vertex order and hold output under backpressure.
The descriptor remains active until every result is consumed; configuration
writes while active are rejected. Abort/reset discard work. Read data is
registered on the peripheral edge before the final word pops its FIFO entry,
matching the CPU's falling-edge RAM interface. The original combinational
response build was cancelled before deployment; the corrected interface passes
real CPU tests against the production C transform/plane functions.

`rtl/geometry_worker.sv` is selected by `SOC_GEOMETRY_WORKER`. CPU feature bit 1
and GW ABI 0x47570101 advertise it through MMIO and UDP status. Its page is separate
from existing graphics registers. `firmware/include/geometry_worker.h` streams
at most four outstanding vertices and copies results into the existing render
scratch buffer. `world.c` retains its original kernel when the capability is
absent. No game model, collision, camera, animation, clipping intersection,
GPU command layout, SDRAM master, cache policy or clock changes are introduced.
The v1 planes are the shared renderer's existing policy; other frustum policies
require an adapter or a versioned extension, not silent reinterpretation.

Normal packages remain compatible. `--geometry-offload` adds a versioned CPU
capability requirement checked before BEGIN, and a distinct package filename.
The mandatory specialized-C/ISA audits still target RV32I plus MUL only.
The candidate normal CPU binary is 26,848 bytes, versus 26,332 in control;
its 883,124-byte asset segment has the same baseline hash.

```powershell
.\scripts\run.ps1 geometry_vectors.py
.\scripts\run.ps1 build_geometry_probe.py
.\scripts\run.ps1 soc.py sim --simulator modelsim --geometry-worker `
  --tests geometry_worker_tb,cpu_geometry_tb
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json `
  --terrain-direct --packed-gfx --integer-mul --geometry-offload
# Add --profile-detail for the instrumented package.
.\scripts\run.ps1 build_geometry_worker.py both
# Run game equivalence/canonical GPU replay before normal gated profiling:
.\scripts\run.ps1 measure_geometry_worker.py
```

The optional `--pending-equivalence` measurement mode was used for provisional
profiling while the long CPU simulation ran. It automatically restores Stage 4;
promotion separately requires exact game/GPU output, fitted timing/coverage,
asset identity and measured ordinary CPU benefit. No provisional result was
selected before those checks passed.

## Verification and measured results

The independent wide-integer oracle covers 1,152 vertices in ten descriptors,
including signed rounding, wraparound and frustum boundaries. Queue tests cover
backpressure, count bounds, active configuration ownership, reset and abort.
The actual RV32I CPU/RAM/MMIO adapter agrees with the original production C
kernel on all probe inputs. The probe audits 467 instructions, with one static
MUL instruction and no unsupported M operations. Packed MMIO and SDRAM RTL
regressions also pass; 42 host tests cover shared-world/terrain behavior and
loader/transport capability gates.

Three complete standing game command streams match exactly through real CPUs,
caches and SDRAM, including actors. The fixture uses controlled decoder
backpressure and immediate presentation acknowledgement; it is not a timing/FPS
measurement. Replaying both streams through the unchanged Stage 4 GPU yields
identical color/depth/palette and 1,332 ordered submitted triangles across three
frames. A slower combined CPU+GPU simulation was abandoned and is retained
separately, never counted as a pass. This is not complete-level traversal or a
physical framebuffer comparison.

### Fitted resources and timing

| Metric | Control | Worker | Difference |
| --- | ---: | ---: | ---: |
| Logic elements | 24,185 | 26,557 | +2,372 |
| Logical memory bits | 2,659,684 | 2,659,688 | +4 |
| M9Ks | 366 | 366 | +0 |
| Physical block-memory bits | 3,373,056 | 3,373,056 | +0 |
| 9-bit multiplier elements | 80 | 92 | +12 |
| PLLs | 2 | 2 | +0 |
| Worst setup slack (ns) | +0.623 | +0.424 | Both pass |
| Worst hold slack (ns) | +0.105 | +0.128 | Both pass |

Both images pass all reported timing checks at unchanged clocks, with zero
unconstrained setup/hold clocks and input/output paths. No Fmax or power gain
is claimed. Queues use fitted logic; M9Ks remain 366/432.

### Physical ordinary standing game

| Metric | Control trials | Worker trials |
| --- | --- | --- |
| CPU update/render cycles | 905,274, 905,273, 905,274 | 648,969, 648,906, 648,906 |
| Observed FPS | 29.785, 29.868, 29.969 | 30.082, 30.075, 30.069 |

Median CPU update/render falls 905,274 to 648,906 cycles: 28.319%
less, or 18.10548 to 12.97812 ms at configured 50 MHz. This is the
ordinary binary, not an instrumented estimate. Observed FPS stays around 30;
uncapped FPS was not measured and gameplay cadence was not changed.

### Detailed profiles and paired kernel probe

| Transform/outcode scope | Control | Worker |
| --- | --- | --- |
| Cycles | [312328, 312333, 312333] | [54939, 54946, 54939] |
| Calls | [8, 8, 8] | [8, 8, 8] |

Scope medians are 312,333 and 54,939 cycles (82.410% less), including
configuration, source reads, input writes, polling and returned-result copies.
Detailed control frame IDs are [251, 251, 251]; worker IDs are
[251, 252, 251]. Matched frame 251 preserves all seven GPU events:
444 submitted, 4 clipped, 195 culled, 263,013 bounding-box pixels, 90,955 inside,
5,999 rejected and 84,956 written. Worker frame 252 has a different actor pose
and is preserved separately, not treated as a matched frame-251 comparison.
Instrumented timings are not substituted for ordinary CPU time.

The same candidate CPU also measures the original kernel and complete adapter
using static on-chip vertices. All three complete probe repeats are identical:

| Vertices in descriptor | Original kernel cycles | Adapter cycles |
| --- | ---: | ---: |
| 1 | 320 | 246 |
| 127 | 37,742 | 5,523 |
| 128 | 38,039 | 5,565 |

The other seven 128-vertex descriptors also report 38,039 / 5,565 cycles.
These are synthetic on-chip-data costs, not SDRAM game-frame savings. There are
15 complete raw comparative trials (3 paired probes plus 3 ordinary and 3
detailed resets per hardware). Three earlier exploratory probe resets have
printed timing pairs and restoration logs preserved separately; their unprinted
counters/status were not reconstructed.

## Selection, artifacts and limits

Stage 5 is accepted as an optional shared geometry upgrade. Selected SOF:
`build\quartus-arch-stage5-worker\ArchStage5SoC.sof`, SHA256 `e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14`.
Normal worker-enabled packed Mario is loaded. CPU/assets upload and readback
passed; initialized/released CPU frames advance 2 to 32 over one second,
with CPU feature bit 1 set and GPU features 3. Exact Stage 4 restoration was
verified after both exploratory and comparative measurements.

Retain Stage 4 as rollback. The next reassessment should use the remaining
clipping and command costs; do not infer an uncapped FPS, power, complete-game
or maximum-frequency improvement from this standing-view CPU reduction.

[Measurements](benchmarks/arch-upgrade-001-stage-5/measurements.json),
[raw evidence/hash manifest](benchmarks/arch-upgrade-001-stage-5/manifest.json)
and [source provenance](benchmarks/arch-upgrade-001-stage-5/provenance.json).
