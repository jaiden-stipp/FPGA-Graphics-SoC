# ARCH-UPGRADE-001 Stage 2A: packed command submission

Implemented and measured October 11, 2026. Source baseline **460957e**, implementation **2f226d6**. Stage 2A adds atomic one-to-four-byte CPU-to-GPU MMIO enqueue, with the original byte path retained. Stage 2B command DMA is **not implemented**. Ordinary uninstrumented standing Mario improves its update-plus-render timer by **0.864%**, with unchanged approximately 30 FPS; the larger detailed-profile savings below are not the ordinary game improvement.

## What changed

The CPU previously performed one MMIO store per command byte. Packed firmware assembles up to four bytes and submits them with one store; exact tails use the one-, two- or three-byte register. The hardware either accepts the complete group or accepts none, preserving order through the existing CRC-checked decoder. Four banks implement the existing 256-byte FIFO without increasing capacity or decoder bandwidth.

`rtl/soc_mmio.sv` implements the banks, atomic capacity check and capability bit. `firmware/src/gfx.c` implements word assembly, bounded readiness checks, conservative capacity reservations, CRC and tails. `firmware/include/soc.h` defines the addresses. `scripts/soc.py` adds `--packed-gfx` and required package metadata; `load_game.py` and `profile_cpu.py` enforce that metadata. `udp_memory_loader.sv` advertises CPU/GPU features in the last two formerly reserved STATUS words, allowing a read-only check while the game runs. Older status replies contain zero and are rejected before upload. `soc_memory.sv` needs no change.

Models, source geometry, collision, gameplay, camera, simulation timestep, cache and clock settings are unchanged. Fractional terrain drawing remains optional, and original capacity packing/direct terrain rendering remain selected. See [register, ordering and ownership contract](gpu-packed-enqueue.md).

## Ordinary-software confirmation

Three additional trials per mode run without optional CPU/detail/fine profiling. The ordinary `portable_main.c` timer spans **update plus render**, unlike the render-only atomic profile. Its live values are read after loader hold and are not an atomic completed-frame publication; no derived render-only claim is made.

| Ordinary transport | Update + render cycles, all trials | Median update + render | Observed FPS, all trials |
| --- | --- | ---: | --- |
| Legacy | 913221 / 913166 / 913166 | 18.26332 ms | 29.791 / 29.868 / 29.969 |
| Packed | 905274 / 905274 / 905273 | 18.10548 ms | 29.969 / 30.069 / 29.868 |

The median reduction is **7,892 cycles / 0.15784 ms / 0.864%** in this standing view. Frame timers stay near 1,668,293 cycles and the saved CPU time becomes additional presentation waiting. Detailed profiling includes per-byte FIFO-wait bookkeeping and changes code generation; packing reduces that instrumentation work as well as actual transport work. Do not extrapolate the profiled 5.394% render reduction to ordinary gameplay or other scenes.

## Primary physical comparison

Three standing-spawn trials per configuration on the **same final Stage 2A image**, at 50 MHz, using identical 883,124-byte castle assets. These are atomic completed-frame snapshots with optional detailed profiling, not route distributions. All primary snapshots are frame 251 at position (-1328, 260, 4664), with 242 commands and 7,011 bytes.

| Transport | Render cycles, all trials | Median CPU render | Command cycles, all trials | Median command time |
| --- | --- | ---: | --- | ---: |
| Legacy byte | 957403 / 957403 / 957403 | 19.14806 ms | 281882 / 281882 / 281882 | 5.63764 ms |
| Byte batching | 961268 / 961268 / 961268 | 19.22536 ms | 284788 / 284788 / 284788 | 5.69576 ms |
| Packed | 905765 / 905755 / 905765 | 18.11530 ms | 230481 / 230481 / 230481 | 4.60962 ms |

Packed submission reduces median command cycles **18.235%** and median CPU render cycles **5.394%** versus legacy. Batching alone increases command time 1.031% and render time 0.404% in this view. These are transport/hardware-plus-firmware results; no isolated benefit from banking alone is claimed.

All primary snapshots have identical seven GPU raster-event counts: 444 submitted triangles, 4 clipped, 195 culled, 263,013 bounding-box pixels, 90,955 covered pixels, 5,999 depth rejections and 84,956 writes. FIFO-capacity waiting is zero in every standing snapshot. Observed FPS remains approximately 30 under existing cadence. CPU and GPU spans overlap; increased swap wait after earlier CPU completion is not extra useful work or an FPS regression.

## CRC, checks and writes

Three fine-profile trials per mode produce the following spans and invocation counts. Fine timers alter code generation, register pressure and scheduling, and have significant work outside the measured nested spans. Word assembly and loop/function overhead are not fully represented here. Compare these diagnostics with the primary coarse spans, rather than adding them into a frame-time prediction.

| Fine scope | Legacy cycles / calls | Batched cycles / calls | Packed cycles / calls |
| --- | ---: | ---: | ---: |
| CRC updates | 175019 / 6527 | 157858 / 6527 | 154228 / 6527 |
| Checks | 126198 / 7011 | 101300 / 7011 | 31404 / 1872 |
| Writes | 77121 / 7011 | 77121 / 7011 | 20592 / 1872 |

Packed write invocations fall from 7,011 to 1,872 (**73.299% fewer**) for the sampled frame. CRC still performs 6,527 updates: 7,011 wire bytes minus two CRC bytes for each of 242 commands. The CRC algorithm is unchanged; the different measured CRC spans do not represent CRC hardware acceleration. Existing `status_reads` counts address 0x04; packed/batched readiness uses 0x08, so zero counted status reads does not mean no readiness checks.

Legacy fine frames are 167 / 166 / 167, batched are 167 / 167 / 167, packed are 251 / 250 / 251. The fine builds run approximately 20 / 20 / 30 FPS respectively because instrumentation itself changes frame cost and update cadence. That is **not an ordinary-game FPS improvement** and these frames may have different animated poses.

## Hardware cost and timing

| Fitted result | Stage 1 candidate | Final Stage 2A candidate | Difference |
| --- | ---: | ---: | ---: |
| Logic elements | 22,533 | 22,675 | +142 |
| Logical memory bits | 2,659,668 | 2,659,684 | +16 |
| Physical M9K blocks | 351 / 432 | 354 / 432 | +3 |
| Physical memory implementation bits | 3,234,816 | 3,262,464 | +27,648 |
| Embedded 9-bit multiplier elements | 80 | 80 | 0 |
| PLLs | 2 | 2 | 0 |
| Worst multicorner setup slack | +0.364 ns | +0.182 ns | Both pass |
| Worst multicorner hold slack | +0.088 ns | +0.126 ns | Both pass |

The Stage 2A image also contains Stage 1's optional registered fractional-mesh extension. Against the accepted ScreenEdges image it adds **921** logic elements and **16** logical memory bits, including both extensions; do not attribute that combined cost to packed enqueue alone. Primary software comparisons all use the same Stage 2A image. Clock settings are unchanged, and timing slack is not a measured Fmax or power claim. Setup/hold are fully constrained; the worst setup path is in CLOCK_50 and worst hold in the fast-corner Ethernet receive domain.

## Correctness, scope and unsuccessful attempts

Fifty-nine host tests pass. The packed FIFO scoreboard covers depths 2, 3, 4, 5, 12 and 256, tails, wraparound, randomized backpressure, simultaneous pops, atomic rejects, invalid sizes and reset. Native tests compile actual `gfx.c` in three modes and independently compare every payload length 0..255 against CCITT-FALSE framing and expected store counts. Existing MMIO, memory, loader and MUL RTL regressions pass. All firmware variants pass the specialized instruction/subset audits.

Full packed-MMIO replays match preserved references exactly for seven castle terrain frames, two Quake static views and eight authored fixtures: complete color/depth/palette and ordered submitted triangles. Castle includes all 1,573 ordered submitted triangles. These captures exclude animated actors and game-specific transition behavior; they do not prove full-level acceptance or reproduce actual CPU throughput. The authored fixtures do not establish maximum triangle-queue saturation. Physical upload/readback and continued frame progress are separate checks.

The first synthesis attempt failed on Quartus 18.1's inline-genvar syntax and was corrected before a SOF existed. ModelSim's unsupported memory-index function form was replaced with equivalent explicit indexing. The initial physical packed preflight failed because UDP READ forbids MMIO and requires loader hold; no packed game was uploaded. The corrected implementation uses existing STATUS fields and retains loader address/hold restrictions. The initial fitted/programmed image and failed preflight logs are preserved separately; all final primary comparisons use the rebuilt status-capable image.

## Deployment and moving diagnostic

Normal unprofiled `mario-castle-sdram-direct-packed-mul.package.json` is loaded on the final Stage 2A FPGA image. CPU image upload/readback passes; its identical immutable SDRAM assets were reused after full readback in the preceding trials. Final STATUS reports initialized SDRAM, CPU released, CPU features 0x80000001, GPU features 3, and frame progress **56 to 86** over the one-second check. This is game progress, not physical framebuffer readback.

Three packed detailed moving diagnostics finish near (-1088,260,3920), (-1136,260,3944) and (-1088,260,3944), with zero FIFO-capacity wait and no startup/submission failure. Their host-timed route is not cycle-identical, there is no matched legacy movement comparison, and no movement speedup or full castle traversal claim is made. Full actor, mission-transition and physical framebuffer acceptance remain pending from Stage 0.

Packed is accepted as an **optional reusable transport** with a small ordinary standing-view CPU benefit. It is selected in the loaded Mario package, while global build defaults retain legacy transport. Neither fractional terrain packing nor DMA is promoted by this experiment.

## Reproduce and inspect

Run from the repository root with the existing configured LLVM/ModelSim/Quartus tools:

```powershell
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --integer-mul --packed-gfx
# Add --profile-detail, or --profile-fine, for the corresponding diagnostic build.
# Replace --packed-gfx with --batch-gfx or omit it for comparison controls.
.\scripts\run.ps1 soc.py sim --tests soc_mmio_tb,packed_mmio_tb,soc_memory_tb,udp_loader_tb,cpu_mul_tb
.\scripts\run.ps1 test_packed_gfx.py
.\scripts\run.ps1 replay_render_route.py --world build/castle/world.json --route docs/benchmarks/arch-upgrade-001-stage-0/castle-orbit-route.json --world-source docs/benchmarks/arch-upgrade-001-stage-0/baseline-world.c --legacy-packing --packed-mmio --out build/replay-packed --simulate
.\scripts\run.ps1 compare_render_frames.py build/arch-stage0/castle-camera-before build/replay-packed --out build/packed-comparison.json
```

Generated game assets and SOF binaries remain local. Full replays share `build/render-replay` and must run serially. The archived capture `simulation.log` files use each saved complete packed replay transcript; the replay helper was corrected to choose the packed test log on future runs rather than the stale legacy log. Captured frame/triangle data and comparisons were unaffected. The archived Quartus helper/QSF, physical measurement helper, raw profiles, source snapshots, captures, fit/timing reports and artifact hashes live under [Stage 2A evidence](benchmarks/arch-upgrade-001-stage-2a/manifest.json). Rollback remains `build/quartus-screen-edges/ScreenEdgesSoC.sof` and `build/arch-stage1/baseline/mario-castle-sdram-direct-mul.package.json`.

## Stage 2B reassessment

Historical decision at Stage 2A completion: the follow-up [staging measurement](command-buffer-staging.md) and [Stage 2B experiment](architecture-stage-2b.md) are now complete. DMA remains experimental after an 8.52% ordinary CPU update/render regression; Stage 2A packed Mario is restored. The original reasoning below explains why measurements were required.

Do not implement DMA solely to replace the remaining MMIO stores. Packed enqueue already reduces the tested stores by 73.3%, with no FIFO-capacity wait. CRC still processes every header/payload byte; a DMA engine preserves that work unless the protocol-building contract also changes. Initial SDRAM DMA would require CPU staging writes, independent-master arbitration, response ownership, bounded refresh/burst service, cache/store ordering, exclusive stream ownership and loader cancellation. Those costs have not been measured and could outweigh transfer savings for a 7 KiB frame.

Keep Stage 2B deferred pending a measured staging/buffer prototype and evidence that transfer work limits a representative route. The updated packed detailed render still spends about 312,333 cycles (6.247 ms) in terrain transforms/outcodes and 231,073 cycles (4.621 ms) in clipping. Those and Stage 3's proposed setup/raster overlap deserve measurement before assuming command DMA is the next gain. Geometry stalls overlap raster work and are not a predicted setup-queue speedup.
