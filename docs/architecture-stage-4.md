# ARCH-UPGRADE-001 Stage 4: two adjacent pixel lanes

Implemented, verified and selected on the FPGA. GPU throughput improves in the
measured workloads; ordinary standing Mario CPU time and FPS do not improve.

## Baseline and acceptance contract

Accepted source baseline: `0a6434b` (Stage 3 setup/raster overlap).
Accepted image: `build/quartus-arch-stage3-overlap/ArchStage3SoC.sof`.
SHA256: `eb28b7007c48fc799ec729655d83a823112ea15c73a06cac665c32e9f1037f62`.
Normal packed Mario package: `build/mario-castle-sdram-direct-packed-mul.package.json`.
CPU binary SHA256: `4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda`.
Assets SHA256: `afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6`.

This baseline is recorded before Stage 4 hardware edits. Keep clocks, game logic,
assets, command ABI and the rejected command DMA path unchanged. Stage 4 is
optional until correctness, fitting, timing and physical trials pass.

The candidate rasterizes adjacent even/odd X pixels in the same ordered triangle.
Each lane has its own depth test and parity bank. Bank address is
`y * (FRAME_WIDTH/2) + (x >> 1)`; odd bounds mask the unused lane. Vertex-extrema
depth clamping and strict greater-than depth testing remain unchanged.
Depth reads explicitly forward a simultaneous same-address write. Triangle drain
precedes the next ordered triangle. Clear owns both banks exclusively and clears
them together. VGA registers read parity alongside read validity, preserving the
existing framebuffer/palette display latency.

Pixel counters must count pixels (0..2 per cycle), while activity counters count
cycles. Banking changes clear duration as well as raster duration; report both
separately. Compare exact color/depth/palette results and submitted triangle order.
Check odd bounds, equal depths, winding, shared edges, reset, clear, bank parity,
read/write bypass, asynchronous display clocks and page swap before promotion.

Stage 4 is accepted as an optional upgrade after the validation and measurements
below. The global single-lane fallback remains available; the selected board image
uses two lanes with normal packed Mario. DMA remains disabled.

## Implementation and reproduction

Baseline commit: `8082afd`; initial implementation: `b465b03`; Quartus-compatible
bank generation and measurement/coverage integration: `721fada`.

`scripts/gpu_pixel_lanes.py` extends the generated renderer boundary. The setup
producer and two-record queue remain the Stage 3 implementation. The consumer
aligns each row's origin to even X, subtracts one original arithmetic step when
the left bound is odd, evaluates both pixels, and advances the row by two steps.
Lane masks prevent either endpoint from escaping the original bounding box.
Both independent `depth_test_stage` instances drain before the next triangle.
Depth interpolation retains the original signed widths, rounding, vertex-extrema
clamp and strict comparison. Different triangles never race each other.

`zbuffer_banked.sv` maps even and odd lanes to independent RAM instances. Its
registered forwarding flag/data overrides the RAM result on a simultaneous
same-address read/write, preserving the synchronous response latency. This avoids
using the primitive's unspecified mixed-port result. `framebuffer_banked.sv`
banks each page in the same way, registers VGA read parity alongside validity,
and leaves page ownership with the existing page-swap controller. The generated
VGA adaptation preserves the original coordinate, synchronization and palette
pipeline. Clear writes both banks in parallel with exclusive ownership.

The generated performance counter inputs accept 0..2 pixels per cycle. The
public 13-word statistics layout and byte/packed command interfaces are unchanged.
`SOC_GPU_TWO_PIXEL_LANES` selects Stage 4; without it the generated wrappers
retain the original single-lane RAM/raster behavior. No game-specific geometry,
collision, camera, animation or package changes are required. The selected
hardware still rasterizes 320x240 and doubles it for 640x480 VGA.

Pinned upstream files stay untouched. Generated RTL is reproducible with
`soc.generate()` and is snapshotted with hashes in the experiment evidence.
The Stage 3 build entry point also understands the extended generated interfaces.

```powershell
.\scripts\run.ps1 build_pixel_lanes.py both
# Only after both fits, timing and exact replay gates pass:
.\scripts\run.ps1 measure_pixel_lanes.py
# Differential raster and real RAM tests:
.\scripts\run.ps1 soc.py sim --full --simulator modelsim `
  --tests pixel_lanes_tb,pixel_banks_tb --work-dir build/stage4-check
# Replay an already captured packed stream through the candidate:
.\scripts\run.ps1 replay_render_route.py --capture-only --packed-mmio `
  --setup-overlap --two-pixel-lanes --out build/arch-stage4/castle-dual --simulate
```

The matched control is Stage 3 overlap with DMA disabled; the candidate adds the
two-lane macro with the same clocks. Build scripts gate assembly on reported
timing slack. Physical measurement additionally checks unconstrained path
coverage and restores the exact accepted Stage 3 image and normal packed Mario
in a `finally` block. Synthetic probe bytes must match Stage 3 before trials run.

Tool/harness findings retained with the evidence: Quartus 18.1 rejected inline
`genvar` declarations accepted by ModelSim; separate declarations fixed it.
The original screen/depth coverage benches observed only the first lane and
reported half the pixels missing. Both lanes now feed the same original
assertions; the discarded harness failure is preserved, not a hardware result.

## Measured results and selection

Fifteen distinct affected RTL tests pass, plus six packed/replay host tests.
The differential raster test compares exact ordered writes, final color/depth
memories and pixel-event totals across 180 saturated and 180 deterministic random
faces, with full-queue backpressure and reset. Real RAM tests cover asynchronous
display parity, stored depth, explicit read/write forwarding, invalid requests,
parallel clear ownership and reset. The updated edge/depth tests also pass with
the Stage 3 fallback. Full-pipeline replays cover 7 castle, 2 Quake and 8 edge
fixture frames: exact color, depth, palette, submitted triangle order and all
seven triangle/pixel event counts match the accepted Stage 3 captures. These
replays exclude full actor/transition behavior and physical framebuffer readback.

### Fitted hardware at unchanged clocks

| Metric | Matched Stage 3 control | Stage 4 | Difference |
| --- | ---: | ---: | ---: |
| Logic elements | 23,789 | 24,185 | +396 |
| Logical memory bits | 2,659,684 | 2,659,684 | +0 |
| Physical M9Ks | 354 | 366 | +12 |
| Physical block-memory bits | 3,262,464 | 3,373,056 | +110,592 |
| 9-bit multiplier elements | 80 | 80 | +0 |
| PLLs | 2 | 2 | +0 |
| Worst setup slack (ns) | +0.533 | +0.623 | Both pass |
| Worst hold slack (ns) | +0.087 | +0.105 | Both pass |

Both images report zero unconstrained setup/hold clocks and input/output paths.
All reported timing checks pass. Banking consumes 12 additional M9Ks despite
unchanged logical capacity; the candidate uses 366/432 and leaves 66 blocks.
No clock increase, maximum-frequency gain or power reduction is claimed.

### Physical synthetic resident-mesh probes

The byte-identical 2,376-byte RV32I probe runs 128 repeated indexed triangles at
three projected sizes. Its 580 emitted instructions pass the ISA audit. Each
image has three reset trials; every value in the table repeats identically in
all three trials, with equal triangle/pixel events. Times are cycles at 50 MHz.
`raster_cycles` is the busy union, not exclusive pixel traversal.

| Projected bounding box | Raster busy: control | Raster busy: Stage 4 | Before swap wait: control | Before swap wait: Stage 4 | Reduction before swap wait |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5x5 | 8,576 | 7,296 | 98,408 | 59,998 | 39.031% |
| 33x33 | 139,815 | 72,231 | 216,820 | 110,836 | 48.881% |
| 65x65 | 541,223 | 274,983 | 618,228 | 313,588 | 49.276% |

Clear is 76,800 cycles in control and 38,400 in Stage 4 in every trial.
The largest probe saves 304,640 cycles before swap wait: 38,400 from parallel
clear and 266,240 additional cycles, matching its raster-busy reduction. The
tiny probe saves 38,410 cycles; almost all of that comes from clear, so it does
not demonstrate a comparable geometry/raster throughput improvement. The total
GPU counter includes VGA wait; shorter useful work can increase that wait.
These synthetic percentages are not game FPS improvements.

### Ordinary and detailed standing Mario

Same unprofiled firmware and assets, three reset trials per image:

| Metric | Control trials | Stage 4 trials |
| --- | --- | --- |
| CPU update/render cycles | 905,274, 905,274, 905,274 | 905,336, 905,274, 905,274 |
| Observed FPS | 29.882, 30.062, 29.781 | 29.868, 29.882, 29.969 |

Both ordinary CPU medians are 905,274 cycles
(18.10548 ms). The candidate's one
62-cycle variation lies within the previously observed accepted Stage 3 range.
Ordinary timers are not atomic profile snapshots. No ordinary CPU/FPS gain is
supported.

Separate instrumented completed-frame snapshots retain unchanged command
traffic and triangle/pixel events for matched frame 251. Raw frame IDs and
all trials are archived; instrumented time is not substituted for ordinary time.

| Instrumented metric | Control trials | Stage 4 trials |
| --- | --- | --- |
| Frame IDs | 251, 251, 251 | 251, 251, 251 |
| Raster busy cycles | 272307, 272307, 272307 | 142504, 142504, 142504 |
| Geometry stall cycles | 209639, 209639, 209639 | 103099, 103099, 103099 |
| Clear cycles | 76800, 76800, 76800 | 38400, 38400, 38400 |
| CPU render cycles | 905765, 905765, 905765 | 905755, 905765, 905755 |

The representative GPU spans decrease substantially while CPU render work
remains unchanged. Geometry activity/stall counters and raster busy are
overlapping spans and cannot be added into serial frame time. Faster GPU work
does not remove the CPU work or change the existing presentation cadence.

### Accepted artifacts and limits

Selected SOF: `build\quartus-arch-stage4-dual\ArchStage4SoC.sof`. SHA256:
`52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235`.
Matched control SOF SHA256: `125a87d27c7654cc6ce51a4015916f218fa77bd5703a0c66722e62d6c18d4b3c`.
Normal firmware/assets hashes remain those in the baseline contract. Full CPU
and asset upload/readback passed. Final CPU is initialized and released, GPU
features are 3, and frames advance 2 to 32 in the one-second
running check. Rollback to the exact accepted Stage 3 image was verified after
both measurement runs. The selected upgrade remains volatile FPGA programming;
this does not establish physical framebuffer or complete-level traversal
acceptance.

Accepted as a reusable GPU-throughput upgrade with modest additional fitted
logic and explicit bank forwarding, while retaining old packages and single-lane
fallback. Further lane duplication should wait for measured demand: this
standing workload shows no ordinary CPU/FPS gain. Preserve the CPU, game assets
and cadence controls when reassessing the remaining bottlenecks.

[Raw measurements](benchmarks/arch-upgrade-001-stage-4/measurements.json),
[hash manifest and raw evidence](benchmarks/arch-upgrade-001-stage-4/manifest.json),
and [source provenance](benchmarks/arch-upgrade-001-stage-4/provenance.json).
Physical order was candidate then control, with three resets per workload per
image (18 trials total); these are standing/probe trials, not route-time or
complete-game frame-time distributions.
