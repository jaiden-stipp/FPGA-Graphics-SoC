# Post-MUL bottleneck review: POST-MUL-REVIEW-001

Measured October 10, 2026 on the physical DE2-115, source baseline `3f5543574c68d23ee9b03a15f6ecc10103551b8d`. CPU terrain transforms and byte-stream command submission remain the largest measured software sections. The sampled game still completes approximately 30 frames/s; these results support improving render headroom, not a promised FPS increase. No RTL, gameplay, models, clocks or default pacing changed during this review.

## Fresh measurements

Three standing and three movement trials use the existing detailed MUL package, atomic completed-frame counters and original assets. Each trial has stationary warmup and an approximately five-second host frame-progress window. One completed-frame snapshot is captured per trial; this is not a per-frame latency distribution or complete-level traversal benchmark. Movement sends repeating one-second directional inputs; endpoints differ, so movement values are diagnostic medians, not matched-route improvement measurements.

All CPU/GPU counters below run at the configured 50 MHz. Milliseconds and percentages are calculated from measured counters. CPU phase and function timers include profiling overhead. Function scopes and command timing are within the render phase; memory freezes and dependency bubbles are also within that phase and must not be added to it again.

| Measured section | Standing median cycles | Standing ms | Moving median cycles | Moving ms |
|---|---:|---:|---:|---:|
| CPU render/submission phase | 945,873 | 18.91746 | 1,063,163 | 21.26326 |
| Terrain vertex transforms/outcodes | 317,180 | 6.34360 | 317,174 | 6.34348 |
| Command submission | 294,210 | 5.88420 | 385,602 | 7.71204 |
| Triangle classification/clipping | 202,331 | 4.04662 | 213,796 | 4.27592 |
| Animation joint evaluation | 20,179 | 0.40358 | 19,853 | 0.39706 |
| Animation vertex posing | 35,549 | 0.71098 | 35,539 | 0.71078 |
| Chunk selection | 4,443 | 0.08886 | 4,443 | 0.08886 |
| Update phase | 40,352 | 0.80704 | 41,364 | 0.82728 |
| CPU memory freezes during render | 44,775 | 0.89550 | 44,607 | 0.89214 |
| CPU dependency bubbles during render | 29,455 | 0.58910 | 36,490 | 0.72980 |
| Presentation wall interval | 681,243 | 13.62486 | 562,828 | 11.25656 |
| GPU raster-active cycles | 273,637 | 5.47274 | 404,746 | 8.09492 |
| GPU clear-active cycles | 76,800 | 1.53600 | 76,800 | 1.53600 |
| GPU geometry-active, excluding output stalls | 41,702 | 0.83404 | 55,612 | 1.11224 |
| GPU geometry output stalls | 235,959 | 4.71918 | 332,311 | 6.64622 |
| GPU VGA swap wait | 500,665 | 10.01330 | 323,290 | 6.46580 |

Observed standing FPS median is **29.868** (range 29.776–30.062); moving median is **29.882** (29.877–30.069). Captured frame wall intervals are 1,667,597 and 1,667,600 cycles, approximately 33.352 ms. Standing CPU phase/detail counts reproduce the previous MUL experiment; small host FPS-window differences do not establish a regression.

Standing render retires 704,519 instructions, IPC 0.745; moving retires 794,466, IPC 0.747. Memory freezes account for **4.734% / 4.196%** of render cycles and dependency bubbles **3.114% / 3.432%**. Update freezes are approximately 44% of its much smaller phase. These counters do not distinguish cache-hit waits, cache misses and other memory transactions individually; they cannot support attributing all freezes to misses.

Command submission consumes **31.105% / 36.269%** of render time, sends **7,011 / 9,195 bytes** in **242 / 326 commands**, and records **zero software FIFO wait span and zero full-FIFO status reads in all six snapshots**. Submission timing includes CRC, software loops and readiness/error checks as well as writes; it is not the isolated MMIO transfer cost. Clipping includes trivial classification, copies and intersections, but excludes output triangulation/packing and command submission. Transform scope includes source reads, matrix arithmetic and six-plane outcodes. Both views record eight mesh transform batches and 785 source-triangle clipping calls.

## What the GPU counters mean

`render_performance_counters.sv` starts total time at frame start and completes it on swap acknowledgement. Its total therefore includes incoming-command gaps and VGA wait. Median total GPU time is approximately 30.452 ms standing and 30.437 ms moving. Directly taking total minus swap wait per snapshot yields median pre-swap spans of **1,021,922 cycles (20.43844 ms)** and **1,198,569 cycles (23.97138 ms)**; these are elapsed spans, not pure GPU compute time.

`graphics_pipeline.sv` counts geometry stalls when an output is valid and its downstream consumer is not ready. This is GPU pipeline backpressure, not a CPU cache stall or proof that the CPU byte FIFO is full. Raster, geometry and command feeding overlap. Their counters must not be summed as a serial frame-time model. CPU presentation also overlaps GPU completion and contains swap waiting; adding its whole interval to the GPU total would double count work.

`portable_main.c` configures a 1,666,667-cycle simulation period, approximately 30 Hz, and renders once per outer update loop. `vga_page_swap_controller.sv` presents only at vertical blank. The current workload/pacing combination produces approximately 30 FPS; simply changing the tick constant would also change gameplay timing. Captured tick wait is only 18 cycles because previous rendering/presentation already consumes the interval. A decoupled render-cadence experiment would be needed to measure an uncapped throughput ceiling while preserving the simulation timestep. No such ceiling or 60-FPS capability is claimed here.

## Recommended next steps

1. **Preserve a correctness route and then validate terrain GPU offload.** Transforms/outcodes alone cost 6.34 ms. The existing resident path can reduce repeated terrain triangle payloads, but `world.c::matrix()` transforms every vertex during admission/validation and drawing, and the GPU uses a narrower transform/clipping path. Measure those checks, use conservative bounds to prove representability, retain direct fallback, and compare geometry coverage and framebuffers before adopting it. Existing missing-floor/render issues remain unresolved by this performance review. Preserve original geometry and collision behavior.
2. **Split command time into CRC, checks and writes, then prototype packed submission.** The growing 5.88–7.71 ms command share makes this a useful hardware target. Start with a defined packed enqueue feeding the existing decoder, including byte order, tails, free-space reservation and errors. Recheck optional software FIFO reservation on MUL with a controlled original-pose fixture. Earlier software-only batching saved 23,928 command cycles but did not improve FPS; it is historical evidence, not a new post-MUL result. No fourfold speedup or DMA savings prediction follows from the current timer.
3. **Separate clipping fractions/intersections from classification.** `world.c` still executes iterative 12-bit fractions. The measured 4.05–4.28 ms clipping total does not isolate division. Count intersection frequency and time fraction arithmetic first; compare a divider or equivalent integer algorithm only with preserved rounding and plane bounds. An integer DIV instruction is not yet justified by an isolated cost measurement.
4. **Measure the GPU tail if pursuing faster presentation.** Raster activity and downstream geometry stalls increase while moving. Capture last-command arrival, pipeline drain, swap request and acknowledgement on one timeline. That distinguishes command starvation, raster drain and vertical-blank alignment before selecting raster throughput, buffering or scheduling work. Animation is now approximately 1.11 ms and is a lower priority in these views.
5. **Keep cache redesign and superscalar execution secondary.** The measured render freezes are under 0.90 ms; update is more memory-sensitive but lasts under 0.83 ms here. Existing smaller-line experiments favored 32 bytes for geometry. A larger FIFO has no observed capacity wait to fix. Wider CPU issue needs instruction-dependency evidence and cannot be justified by the many retired instructions in presentation polling.

For the next implementation, retain this source revision and identical assets as the comparison baseline, test a fixed pose/route and verify decoded commands/framebuffer results. Compare phase cycles, useful retirement, stall categories, GPU drain/swap timing, frame-progress distributions, fitted resources and timing. Do not select changes using FPS alone while the current cadence remains approximately 30 Hz.

## Reproduction and evidence

Run from the repository root, with the existing MUL FPGA image programmed:

```powershell
.\scripts\run.ps1 profile_cpu.py build/mario-castle-sdram-direct-profile-detail-mul.package.json --symbols build/mario-castle-sdram-direct-profile-detail-mul.symbols.json --restore build/mario-castle-sdram-direct-mul.package.json --out build/post-mul-review/standing.json --trials 3 --reuse-immutable-assets
.\scripts\run.ps1 profile_cpu.py build/mario-castle-sdram-direct-profile-detail-mul.package.json --symbols build/mario-castle-sdram-direct-profile-detail-mul.symbols.json --restore build/mario-castle-sdram-direct-mul.package.json --out build/post-mul-review/moving.json --trials 3 --moving --reuse-immutable-assets
```

The harness verifies CPU/assets on first transfer, preserves atomic CPU/detail frame IDs and restores normal animated, unprofiled MUL Mario after each case. Asset reuse is restricted to the matching immutable SDRAM segment. No FPGA reprogramming took place. Existing SOF SHA-256: `84de9a3059e5a40957438df348da434c05e462955e60528491f2f2ac6713484b`.

[Measurements and artifact hashes](benchmarks/post-mul-review-001/measurements.json), [standing raw trials](benchmarks/post-mul-review-001/standing.json) and [moving raw trials](benchmarks/post-mul-review-001/moving.json) retain all observations. Relevant source snapshots and the summarization helper are archived beside them. This is an assessment, not a newly measured optimization or fix.
