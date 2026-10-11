# ARCH-UPGRADE-001 Stage 3: setup/raster overlap

Status: implemented, verified, measured and loaded with normal packed Mario. Serial remains the global fallback.

The optional upgrade overlaps setup with pixel traversal using two ordered records.
A medium synthetic resident-mesh case uses 2.176% fewer GPU cycles before swap
waiting; ordinary standing CPU time and approximately 30 FPS are unchanged.
Fitted cost is +1,010 logic elements versus matched control, with unchanged RAM,
multiplier and PLL use. All 17 saved replay frames match exactly.

Source baseline: f8b9c45. Accepted board image: Stage 2A packed, SHA256
917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32.
Normal firmware SHA256: 4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda.
Immutable castle assets SHA256: afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6.

Experiment: retain existing arithmetic, split setup from raster traversal, and
place two stable ordered records between them. Preserve strict depth comparison,
per-triangle depth drain, command order, clear and swap barriers. Test both
serial and overlapped modes with identical packed firmware and clocks. Keep the
rejected command DMA disabled in both physical variants. No improvement is
claimed before measurement. Queue depth two is an experiment, not an optimum.

Internal record contract v1: viewport bounds (10-bit X, 9-bit Y), three signed
22-bit initial edges and six steps, signed 32-bit depth gradients, signed 36-bit
depth start, vertex depth extrema, color, winding sign, and skip flag. Each
accepted triangle yields exactly one ordered record, including empty/degenerate
triangles. Only one frame can own the pipeline at a time; frame metadata stays
in the existing command processor, and END_FRAME waits for the entire pipeline.

Physical framebuffer, actors and full-level route acceptance remain outside the
existing terrain replay coverage. Report synthetic overlap gains separately
from ordinary game CPU timings, GPU spans and frame cadence.

## Implementation and ordering

`gpu_setup.py` generates `triangle_setup_engine.sv` by extracting the corrected,
pinned renderer's setup arithmetic. Its two signed depth-gradient dividers still
run concurrently, exactly as before. A new producer can compute the next
triangle while `renderer_overlap.sv` scans the active one. Two registered
362-bit records hold completed setup results. The active record is separate,
and a third produced record can wait under backpressure. The queue depth is
not a claim that two entries are optimal.

Records contain all mutable state needed by rasterization: viewport bounds,
edge starts and signed steps, winding, depth gradient/start, vertex extrema,
color and a skip flag. The consumer never reads the next producer triangle's
vertices. Invalid bounds and degenerate triangles produce ordered skip tokens.
The existing inclusive edge tests, fixed-point truncation, depth-extrema clamp,
strict greater-than depth comparison and per-triangle depth drain are preserved.

`graphics_pipeline.pipeline_idle` now checks renderer **busy**, rather than
input-ready. Input-ready can be true while an earlier triangle is still drawing.
Busy includes the producer, both queue entries, active traversal and pending
depth work. END_FRAME still waits for transform/FIFO work and this entire busy
union before page swap. Clear ownership remains unchanged. Only one frame owns
the pipeline; no frame interleaving or triangle reordering is introduced.

The public command stream/MMIO/firmware ABI remains unchanged. Internal
setup-record v1 is not an externally uploaded packet format. Existing packed,
legacy and game packages still use the same interfaces. The experiment is
selectable using `SOC_GPU_SETUP_OVERLAP`; serial is the global default. Both
physical variants use `SOC_DISABLE_COMMAND_DMA` to reproduce the accepted
cache-to-controller connection and exclude Stage 2B's rejected experiment.

## What the measurements mean

Simulation-only diagnostic counters expose setup work, output blocked by a
full queue, raster idle while waiting for setup, actual setup/raster overlap,
and maximum setup-queue occupancy. They are excluded from synthesis and do not
add physical MMIO registers. A held ready/valid record is asserted stable.
The whole renderer's existing `raster_cycles` counter measures the **busy union**
of setup, queued work, traversal and depth drain; it is not an exclusive pixel
scan timer or a sum of the simultaneous engines.

Physical resident-mesh probes send 128 repeated original-format indexed faces
at each of three projected sizes. These are synthetic fixtures; equal-depth
repeats deliberately exercise ordered rejection. The same RV32I packed firmware
runs on each image. Existing GPU event counters must agree; three trials per
image include reset, upload/readback and completed frame IDs. GPU total minus
swap-wait includes clear, command/geometry work and final drain. It must not be
reported as raster-only time or game FPS.

Ordinary standing Mario uses the unchanged uninstrumented packed firmware.
Its live CPU timer covers update **plus** render and is non-atomic. Detailed
profiles use the unchanged instrumented firmware and completed-frame publication.
Their counters are diagnostic and must not replace the ordinary result.
CPU/GPU spans overlap and cannot be added into serial frame time. Every board
comparison finishes by restoring the exact accepted Stage 2A image and normal
Mario, with full immutable asset readback and frame progress verified.

## Reproduction

```powershell
# Generate the reusable adaptation from pinned sources.
.\scripts\run.ps1 soc.py bootstrap
# Differential test uses serial and overlap explicitly in one simulation.
.\scripts\run.ps1 soc.py sim --full --tests setup_overlap_tb
# Both fixed-clock physical variants; assembly is gated by all reported slack.
.\scripts\run.ps1 build_setup_overlap.py both
# Run only after both fits, timing and full-frame comparisons pass.
.\scripts\run.ps1 measure_setup_overlap.py
# Example saved-stream differential replay:
.\scripts\run.ps1 replay_render_route.py --out build/arch-stage3/castle-overlap --capture-only --packed-mmio --setup-overlap --simulate
```

The replay example requires its already prepared `input.hex`, `input.meta` and
`input.json`; prepare/copy the same accepted stream before comparison. Full
replays share one scratch directory and run serially. Quartus builds also run
serially. There is one physical-board owner. `--setup-overlap` and
`--disable-command-dma` are available on `soc.py sim` for configuration checks.

## Verification and initial tool failures

Eleven affected RTL tests pass: differential setup/raster, full-screen edge
coverage, distant depth coverage, fractional decoder/mesh, MMIO, packed FIFO,
CPU RAM/MMIO, SDRAM memory, loader and integer MUL. Six existing packed/replay
host tests pass. Differential direct-render tests cover 180 saturated faces and
180 deterministic random faces, opposite winding, offscreen/degenerate faces,
variable depth, equal-depth ordering, full-queue output stability and reset
with active/queued setup work. Ordered pixel writes and final depth/color agree.

The first diagnostic assertion counted a new handshake before busy updated;
the corrected check accounts for the current handshake. ModelSim's seeded
random calls yielded degenerate repeated fixtures; the reset fixture now uses
an explicit deterministic generator and asserts full queue coverage. Initial
Quartus failures concerned a simulation-only hierarchical state alias and a
missing experimental arbiter source in the disabled-DMA build. The alias is
excluded from synthesis, and disabled DMA now restores the original direct
controller topology. Packed replay also exposed old runtime references to an
absent DMA generate scope; stimulus controls now exist outside that scope.
Failed logs are retained. No timing-failing hardware is programmed.

Full-frame replay coverage includes shared terrain and authored fixtures,
not full game actors, room transitions, physical framebuffer capture or
complete-level collision/traversal acceptance. No power or maximum-frequency
claim is made.

## Measured results and acceptance

Stage 3 is accepted as an **optional GPU scheduling upgrade**, with serial
fallback retained and the global generator default unchanged. Exact replay
outputs, positive multicorner timing and measured synthetic throughput support
this decision. It does **not** improve ordinary standing Mario CPU time or FPS.
The smallest synthetic case regresses slightly; larger setup queues and more
parallel arithmetic are not justified by this experiment alone.

The physical comparison uses a fresh matched serial control, not merely an old
SOF with different generated topology. The control has 22,774 fitted logic
elements versus 22,675 in the original accepted Stage 2A artifact; both retain
the accepted transport/cache/renderer arithmetic and normal firmware. Attribute
the isolated Stage 3 cost against the fresh control, and preserve the original
SOF as rollback. No change of clock, cache, game code or immutable assets is
part of the comparison.

| Fitted quantity | Matched serial | Overlap | Difference |
| --- | ---: | ---: | ---: |
| Logic elements | 22,774 | 23,784 | +1,010 |
| Logical memory bits | 2,659,684 | 2,659,684 | +0 |
| Physical M9K blocks | 354 | 354 | +0 |
| Physical memory implementation bits | 3,262,464 | 3,262,464 | +0 |
| Embedded 9-bit multiplier elements | 80 | 80 | +0 |
| PLLs | 2 | 2 | +0 |
| Worst setup slack | +0.641 ns | +0.311 ns | Both pass |
| Worst hold slack | +0.117 ns | +0.089 ns | Both pass |

Both timing reports have zero unconstrained clocks/input/output setup/hold paths.
Worst setup is CLOCK_50. Worst hold is CLOCK_50 in serial and Ethernet RX in
overlap. All other reported checks pass. Slack is not a measured Fmax gain.

### Physical synthetic throughput

All three trials per image have identical seven raster event counts in each
mesh case. Total cycles differ slightly with VGA phase, but total minus swap
wait is constant within each case. Each case repeats one resident triangle 128
times; projected bounds are 5 by 5, 33 by 33, or 65 by 65 pixels. Geometry
submission and clear are included in work before swap wait. This is a GPU
fixture result, not an original-game speedup.

| Projected bounds | Raster busy union: serial / overlap | GPU total minus swap: serial / overlap | Change before swap wait |
| --- | ---: | ---: | ---: |
| 5 x 5 | 8,320 / 8,576 | 98,406 / 98,408 | +0.00203% |
| 33 x 33 | 144,512 / 139,815 | 221,644 / 216,820 | -2.17646% |
| 65 x 65 | 545,920 / 541,223 | 623,052 / 618,228 | -0.77425% |

The medium and large cases each save 4,824 cycles / 0.09648 ms before swap wait
at 50 MHz. Their raster-busy unions fall 4,697 cycles. The smallest case adds
256 raster-busy cycles and two cycles before swap wait: setup and traversal
cannot usefully overlap when the geometry producer is slower than both. Queue
handoff adds latency in this case. Presenting still waits for VGA; no uncapped
physical FPS claim is supported.

### Ordinary Mario and detailed diagnostics

Serial ordinary update+render trials: **905336 / 905336 / 905274 cycles**; median **905,336 cycles / 18.10672 ms**. Observed FPS: 29.854 / 30.062 / 29.746.

Overlap ordinary update+render trials: **905336 / 905336 / 905274 cycles**; median **905,336 cycles / 18.10672 ms**. Observed FPS: 29.961 / 29.983 / 29.761.


The ordinary medians are equal. Existing frame cadence remains approximately
30 FPS. Do not substitute a detailed-profile or simulated drain reduction for
an ordinary CPU/FPS improvement.

Detailed control frames are 251, 251 and 252; candidate frames are all 251.
Frame 252 has small animation-dependent event differences and is retained in
raw evidence. The two matching serial frame-251 snapshots and all three
candidate frame-251 snapshots have exactly 444 submitted triangles, 4 clipped,
195 culled, 263,013 bounding pixels, 90,955 covered, 5,999 depth rejections and
84,956 writes, with 242 commands / 7,011 bytes. Command cycles remain 230,481
and FIFO-capacity wait is zero. CPU render is 905,755 or 905,765 cycles for those
matched frames; this is instrumentation, not the ordinary timer.

On matched frame 251, geometry-stall cycles fall **238,048 to 209,639**.
Geometry-active union rises **41,441 to 42,366**; this existing counter excludes
selected output-backpressure states and measures a scheduling union rather
than an unchanged arithmetic operation count. Raster-busy union falls
**272,997 to 272,307**. These overlap other CPU/GPU scopes. Completed total
minus swap wait is approximately 991,786-991,791 cycles serial and
990,929-990,934 overlap. The small gain does not change frame cadence.

### Exact simulation replay

Both rebuilt modes exactly match all accepted reference color/depth/palette
samples and ordered submitted triangles: seven castle terrain frames (1,573
ordered triangles), two Quake static frames and eight authored fixtures. These
are fixed saved streams with simulated producer timing, not the game's CPU.

| View | Serial begin-to-swap-request cycles | Overlap cycles |
| --- | ---: | ---: |
| castle 1 | 352,722 | 342,689 |
| castle 2 | 472,850 | 458,564 |
| castle 3 | 426,461 | 413,424 |
| castle 4 | 362,508 | 350,282 |
| castle 5 | 312,103 | 303,694 |
| castle 6 | 413,218 | 405,311 |
| castle 7 | 266,935 | 266,595 |
| quake 1 | 323,723 | 298,254 |
| quake 2 | 340,796 | 310,292 |

In castle frame 1, setup work is unchanged at 6,118 simulated cycles,
setup-related raster waiting falls 6,118 to 1,734, and useful setup/raster
overlap is 4,423 cycles. Maximum setup queue occupancy is two. Producer output
blocked by full queue is 131,440 cycles in that view: long raster work remains
the bottleneck. All timing fields and queue counters are archived. Do not add
blocked, setup, overlap, geometry and raster scopes together as serial costs.

## Evidence and next priority

Implementation commits: 2bf56dd, 8ee9eed, 8bb928c and 0d10359; baseline 6153efa.
The probe passes specialized-C audit and checks all 580 emitted instructions;
no optional M instructions are present. Existing normal/detailed game binaries,
ISA reports and asset hashes are retained unchanged. Eighteen physical trials
cover two images, three workloads and three repeats per workload. Synthetic
cases each include three mesh sizes. Failed elaboration/synthesis logs, both
SOF hashes, compiler commands, source snapshots, full fits/timing, readback and
restoration/deployment identities are preserved in
[raw evidence](benchmarks/arch-upgrade-001-stage-3/manifest.json) and
[measurements](benchmarks/arch-upgrade-001-stage-3/measurements.json).

Resume-safe wording: implemented an ordered two-record triangle-setup queue
with concurrent setup/rasterization on Cyclone IV E, verified exact framebuffer
and depth output across 17 replay frames, and measured 2.176% less GPU work
before swap waiting in a synthetic resident-mesh case at unchanged 50 MHz.
Cost: +1,010 fitted logic elements versus matched serial control, unchanged
RAM/multiplier/PLL use. No ordinary Mario FPS or CPU gain is claimed.

Next: Stage 4's two pixel lanes targets traversal time left exposed by long
triangles. Before implementing it, prove depth/color banking, parity masks,
read-after-write handling and swap barriers. Preserve this optional Stage 3
variant as the measured baseline. Extend actor/transition/physical route
acceptance separately; do not increase queue depth merely because it reaches
full occupancy.

## Selected FPGA image and rollback

Normal unprofiled packed Mario is running on the verified Stage 3 image:
`build/quartus-arch-stage3-overlap/ArchStage3SoC.sof`, SHA256
eb28b7007c48fc799ec729655d83a823112ea15c73a06cac665c32e9f1037f62. Full 26,332-byte CPU and 883,124-byte immutable asset
upload/readback passed. Final STATUS is initialized, CPU released, features
0x80000001 / 3, with frame progress 2 to 32 over the one-second check. This proves
programming/game progress, not physical framebuffer or complete-level acceptance.

Rollback is the exact original `build/quartus-arch-stage2a/ArchStage2ASoC.sof`,
SHA256 917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32,
with the same normal `mario-castle-sdram-direct-packed-mul.package.json` package.
Both experiments exercised this rollback with full readback before final selection.
The fresh matched serial control is independently retained as
`build/quartus-arch-stage3-serial/ArchStage3SerialSoC.sof`. SOFs and full game assets
stay local; hashes, reports, commands and raw measurement/capture evidence are
committed. Stage 4 has not been implemented.
