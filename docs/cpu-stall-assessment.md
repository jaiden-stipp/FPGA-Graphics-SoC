# CPU stall assessment

Assessed October 10, 2026 against baseline commit 5f0d8ff. This assessment changes no hardware, firmware or FPGA state. It uses source inspection and existing measurements; no new performance experiment was run.

## What stops progress

| Cause | Implementation | What is established |
|---|---|---|
| SDRAM transaction | rtl/sdram_bridge.sv; rtl/soc_memory.sv; rtl/generated/RV32I_SoC.sv | soc_stall freezes all five pipeline stages. Hits and misses both use a blocking handshake. The existing controller/bridge simulation measures a 32-byte-line hit at 3 cycles and a cold burst read at 19 cycles. These are simulated transaction latencies, not measured game stall cycles. |
| Load-use dependency | external/rv32i/5-Stage-Pipeline/HazardUnit.sv; rtl/generated/soc_ID_EX.sv | A load whose destination is immediately needed by the following instruction inserts a bubble when the pipeline advances. Forwarding already handles other supported dependencies. |
| Control redirect | rtl/generated/RV32I_SoC.sv | Branch/jump redirection resolves in EX and flushes younger stages. No prediction path is present. Frequency and lost cycles in the game have not been measured. |
| GPU command readiness | firmware/src/gfx.c: send_byte | Each byte polls GPU error/readiness registers before transmission. CRC generation also runs on the CPU. Polling executes instructions; it is not soc_stall. |
| Frame completion | firmware/src/gfx.c: gfx_wait_frame | The CPU polls completion until rendering and presentation finish. This interval mixes remaining GPU work and presentation timing. |
| Simulation pacing | firmware/src/game_runtime.c; firmware/src/portable_main.c | The runtime intentionally waits for the next tick. The frame CPU timer starts after this wait, so it is excluded from that published measurement. |

Instructions are fetched from local RAM, not SDRAM. An instruction cache is therefore not the immediate answer to the current SDRAM wait path. The current cache is 4 KiB, direct mapped, blocking and write through with no write allocation. Keep 32-byte lines: the measured comparison favors them for geometry, while smaller lines provide little or negative benefit on the production collision kernel.

## Existing physical frame evidence

Source: docs/benchmarks/cache-lines-001/candidate32-game.json. Three stationary spawn-view windows with unchanged player coordinates; observed frame rates are 20.246, 20.000 and 20.000 FPS. This is not a traversal benchmark.

The following is the trial-2 published snapshot. Milliseconds are calculated from cycles using the configured 50 MHz clock, not an independently measured oscillator frequency.

| Published interval | Cycles | Derived ms |
|---|---:|---:|
| Update | 44,431 | 0.889 |
| Terrain preparation | 13,595 | 0.272 |
| Terrain draw | 1,264,284 | 25.286 |
| Actor pose upload | 302,500 | 6.050 |
| CPU update plus render/submission | 1,669,508 | 33.390 |
| Presentation wait | 832,988 | 16.660 |
| Frame interval | 2,502,504 | 50.050 |

Stage globals and published frame counters can refer to different frames. Do not sum these rows into an exact decomposition or use them to claim percentages of CPU stall causes. Terrain draw includes computation, asset accesses and command transmission/readiness polling. Presentation wait does not separately identify rasterization and vertical blank waiting.

The deployed package uses WORLD_FORCE_DIRECT=1: CPU terrain transformation/clipping and individual triangle commands bypass the resident GPU terrain mesh path. Actors still use resident GPU meshes. This diagnostic configuration makes terrain submission an important investigation target. It should not be silently switched back while correctness problems remain unresolved.

## Missing measurements

The existing CPU Monitor is inside synthesis translate_off, so its counters are not present on the board. Its stall input counts the load-use hazard signal rather than soc_stall; redirect/hazard signals are not qualified by pipeline advancement and can remain asserted through a memory freeze. Cache busy cycles cover cache activity and may include loader transactions; they are not an exclusive CPU stall counter.

Before selecting a CPU redesign, expose physical counters for active cycles, retired instructions using trace_valid, global memory freeze cycles, advancing load-use bubble events and advancing control redirects. Exclude reset/loading. Count memory freezes first and qualify hazard/redirect events by soc_advance to avoid counting held signals repeatedly. Redirect events are not themselves an exact branch penalty measurement. If bubbles overlap, report the overlap or use pipeline-valid accounting rather than blindly summing causes.

Measure software phases separately: arithmetic/geometry preparation, CRC and command packing, FIFO readiness waiting, frame completion waiting and tick pacing. Publish an atomic completed-frame snapshot. Software polling cycles must not be described as hardware pipeline stalls. Counter overhead should be recorded; identical instrumentation must be used in both baseline and candidate.

## Recommended order

1. Add the above observability and record a reproducible walking/camera route, keeping game assets, input sequence, clock and correctness checks fixed. Preserve the pre-change commit and SOF hashes. This establishes whether the next limit is arithmetic, memory or submission.
2. Investigate CPU-to-GPU submission first because terrain drawing and actor upload are the largest recorded named work phases in the standing view. If readiness waiting or byte transport dominates, evaluate packed word writes or a bulk command queue/DMA. Preserve the game-facing command interfaces. A larger FIFO only helps if measurements demonstrate temporary backpressure; it cannot fix a persistently slower consumer. Validate the resident terrain path before comparing it against direct drawing.
3. Reduce cached-hit bridge latency if measured memory freezes are substantial. This targets a frequently used path without widening CPU issue. Validate byte/halfword loads, sign extension, load-use behavior, loader invalidation and timing. The 3-cycle simulated hit is a baseline, not a promise that a 1-cycle implementation is achievable.
4. Profile fixed_mul and division. They currently use software arithmetic on RV32I and appear in geometry and collision. If they dominate, evaluate integer multiplication before dual issue. An ISA addition requires decode/execute/hazard validation and compiler/runtime changes; explicit fixed_mul helpers will not automatically use new hardware. Measure resources and timing after fitting rather than estimating them.
5. Consider branch handling, instruction scheduling and finally superscalar issue if retirement/stall measurements show enough independent compute work. Dual issue needs additional register-file ports, dependency detection and bypassing, and may reduce achievable clock frequency. It cannot directly eliminate blocking SDRAM fills or GPU polling waits.

No speedup, stall percentage, resource delta or maximum frequency is claimed for these proposed changes. Each implementation should be compared with the same workload and report cycle/frame results, correctness, whole-SoC fitted resources, timing and its commit/bitstream identity.
