# CPU and GPU submission profiling

CPU-PROFILE-001, October 10, 2026. The baseline is commit 7280023, the counter and transport implementation is 02d08ab, and the corrected single-socket measurement harness is b388364. Hardware counters are observational; the optional batching experiment changes software only. Default firmware with both options disabled remains byte-identical to the original Mario binary and asset segment.

## Counter contract

The CPU samples five wrapping 32-bit counters on its rising pipeline edge. Reset/loading excludes all counts. Active cycles count every running clock, retirement uses architectural trace_valid, memory freezes count soc_stall, dependency bubbles count advancing load-use hazards without a control redirect, and redirects count advancing pc_src events. Memory freeze takes precedence: a held hazard or redirect is not counted repeatedly. A redirect is an event, not a measured number of lost retirement slots.

MMIO snapshot write at 0x40000098 latches all seven fields together on the falling CPU edge. Reads stay fixed until the next snapshot. CPU counter ABI at offset 0x80 is 0x43500101. Fields are active cycles (0x84), retired instructions (0x88), memory freezes (0x8c), dependency bubbles (0x90), redirects (0x94), GPU status-register reads (0xa0), and status reads observed while the command FIFO is full (0xa4). The last two count reads of GFX_STATUS, including presentation polling; they do not count GFX_FREE or GFX_ERRORS reads.

Profile firmware brackets tick pacing, update, render/submission and presentation. Counter differences include instrumentation around each phase boundary. They are not disjoint classifications of every lost cycle: retirement can coexist with a dependency bubble upstream, and redirects are separate events. IPC is retired instructions / active cycles. Freeze and dependency percentages use their own phase cycles as denominator.

Command-cycle timing surrounds gfx_command, including CRC, loops, MMIO transmission and any FIFO waiting. FIFO wait span timing starts after the first failed readiness check and ends when readiness returns. It excludes that first check and includes polling/timer overhead; it is not an exact hardware stall counter. It is nested within command timing and must not be added to it. Bytes and commands count successful submissions. Presentation waiting executes instructions and can contain both remaining GPU work and vertical-blank waiting.

Completed frames publish a double-buffered snapshot with the slot index committed last. Holding the CPU during publication therefore leaves a complete prior slot available. Each slot is 53 words: four seven-field phase records, command cycles/FIFO wait span/bytes/commands, tick/update/CPU/present/frame wall intervals, frame ID, configured clock, ABI, then thirteen completed GPU counters. The held live player coordinates can belong to a subsequent partial update; movement snapshots do not claim atomic player-state capture.

## Reproduction

Generate the SoC adapters with the existing bootstrap/generate workflow, then compile a counter-enabled FPGA project using scripts/soc.py quartus-project and build-fpga. Preserve the original SOF first and require successful timing. The isolated project and build helper used for this experiment are archived with the evidence.

Build profiles through the shared game pipeline:

```powershell
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --cpu-profile
.\scripts\run.ps1 soc.py portable-game --project build/castle/game.project.json --terrain-direct --cpu-profile --batch-gfx
```

The resulting stems are mario-castle-sdram-direct-profile and mario-castle-sdram-direct-profile-batched. The measured experiment used a preserved generated scene and separate stems mario-castle-profile and mario-castle-profile-batched; its build helper and hashes identify the exact tested artifacts. Both approaches use the same shared portable runtime and unchanged assets.

Run scripts/profile_cpu.py with package, --symbols, --restore and --out paths. --moving sends a repeating one-second forward/left/back/right pattern after stationary warmup. It is a wall-clock diagnostic, not an identical sequence of simulation ticks across different frame rates. --uninstrumented collects baseline FPS and legacy globals. --reuse-immutable-assets is an explicit opt-in: it verifies complete assets on the first trial, checks they match restoration assets byte-for-byte, then uploads only CPU RAM for later trials and successful restoration. Failed trials restore the complete baseline. Use it only when game asset segments remain immutable.

The harness uses one UDP socket for both controls and loader requests: the response transmitter's completion replies use the last peer port. The first separate-socket attempt timed out, restored the baseline, and is retained as a failed run. No performance number is taken from it.

## Bulk transport experiment

GFX_BATCHED reserves the currently reported FIFO free capacity and sends that many existing byte writes before checking again. Only the CPU produces this stream; downstream pops increase free capacity. Credit is refreshed for every command, commands larger than available capacity refill safely, and error checks remain at refills and command completion. The existing byte order, CRC, decoder, meshes and GPU datapath are preserved. It does not add packed word writes, DMA or a larger FIFO, and remains optional.

The legacy and batched command-stream fixtures verify the same decoded commands, payloads and frame ACK under backpressure. Separate CPU tests verify retirement through an injected eight-cycle freeze, a dependent load and a taken branch; MMIO tests check the snapshot remains stable when live counters change. The active instrumented C configuration passes the specialized RV32I subset audit.

## Results and reassessment

Measured on the physical DE2-115 at the configured 50 MHz clock, with three trials per configuration. Each trial samples approximately five seconds of completed-frame progress after startup and a three-second stationary warmup, then captures one atomic completed-frame profile. Individual runs, input packet schedules and all calculated medians are retained in [measurements.json](benchmarks/cpu-profile-001/measurements.json). The movement route is deliberately a diagnostic: endpoint positions differ, so its snapshots are not a controlled movement-speedup benchmark.

Standing legacy-transport profiles all captured completed frame 167 at the same spawn view. These are measured counters; percentages and milliseconds below are calculated from them.

| Phase | Active cycles | Retired instructions | Memory freezes | Dependency bubbles | Redirect events |
|---|---:|---:|---:|---:|---:|
| Update | 89,033 | 40,995 | 35,706 | 2,782 | 4,775 |
| Render/submission | 1,655,341 | 1,276,552 | 43,886 | 27,421 | 153,741 |
| Presentation polling | 757,604 | 482,133 | 0 | 137,731 | 68,870 |

Render-phase IPC is 0.771, memory freezes account for 2.651% of render cycles, and dependency bubbles account for 1.657%. Update memory freezes account for 40.104% of update cycles, but this sampled update interval lasts only 1.781 ms; rendering lasts 33.107 ms. The update snapshot includes catch-up work, so it is not the cost of exactly one simulation tick.

For this captured interval, cycles equal retirement + memory freezes + dependency bubbles + twice the redirects. This is a consistency check against the five-stage pipeline's two younger-stage flushes; redirects remain event counters, and the relation should not be assumed for arbitrary workloads or a future pipeline.

Presentation makes 68,859 status reads and accumulates 137,731 load-use bubbles while waiting. Improving the instruction throughput of that polling loop would not by itself finish a GPU frame sooner. Keep it separate from useful game computation when choosing CPU optimizations.

All six legacy-transport stationary/movement snapshots record zero full-FIFO status reads. All twelve instrumented snapshots, including batching, record zero software FIFO wait span. This establishes no observed submission backpressure in those captured frames, not that the FIFO can never be full in another scene. Standing legacy submission makes 7,011 status reads for 7,011 bytes in 242 commands; the batching build uses GFX_FREE instead, which is outside the status-read counter.

| Standing profiled interval, median of three snapshots | Legacy bytes | FIFO reservation | Change in cycles |
|---|---:|---:|---:|
| Command submission | 294,210 (5.88420 ms) | 270,282 (5.40564 ms) | -23,928 (-8.133%) |
| Render phase | 1,655,341 (33.10682 ms) | 1,632,369 (32.64738 ms) | -22,972 (-1.388%) |
| Bytes / commands | 7,011 / 242 | 7,011 / 242 | Same |

These are software transport results on the same instrumented FPGA image, not a hardware speedup. Render snapshots vary slightly with animation/frame timing: batched frame IDs are 168, 167 and 167. In matched frame 167, the seven GPU raster-event counts agree: 444 triangles submitted, 6 clipped, 196 culled, 263,682 bounding-box pixels, 91,148 inside pixels, 6,131 depth rejects and 85,017 written pixels. This supplements command-stream simulation and does not replace a framebuffer pixel checksum or comprehensive traversal validation.

| Configuration | Median observed standing FPS | Scope |
|---|---:|---|
| Original FPGA + original firmware | 19.977 | Baseline |
| Counter FPGA + original firmware | 19.931 | Hardware observability control |
| Counter FPGA + profile firmware | 19.915 | Software profiling enabled |
| Counter FPGA + profiled batching | 19.927 | Paired transport experiment |
| Original FPGA + batching without software profiling | 19.857 | Checks whether profiling hides an FPS benefit |

All remain approximately 20 FPS; these short host windows do not establish a meaningful FPS gain or regression. Software instrumentation adds work, and the uninstrumented globals can refer to different frames; do not derive an exact profiling-overhead percentage from them. The original and counter-hardware control firmware have identical CPU bytes and assets. Instrumented/batched packages preserve the original 883,124-byte asset segment, SHA-256 afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6.

Legacy movement snapshots have render memory-freeze fractions of 2.462% and dependency fractions of 1.904%-1.908%. FIFO reservation movement snapshots also show zero measured FIFO wait. Positions and rendered work differ between some trials, so do not publish a movement speedup percentage from their time differences.

Whole-SoC fitted instrumentation cost is measured: logic elements rise from 20,979 to 21,564 (+585); memory remains 2,659,668 bits, embedded 9-bit multiplier elements remain 74, and PLL count remains 2. All reported timing passes at existing clocks; CLOCK_50 setup slack is 0.760 ns and minimum reported summary slack is 0.111 ns. These slack values do not measure maximum operating frequency.

## Reassessed priorities

Follow-up: [individual render-function profiles](render-function-profiling.md) now measure transforms/outcodes, clipping, joint evaluation and vertex posing separately, with physical evidence and an integer-MUL/GPU-offload assessment. The list below records the priorities from the preceding stall/submission experiment.

1. Profile the remaining CPU render work by function: transforms, six-plane clipping/intersections and actor pose evaluation. Subtracting the nested command timer from the legacy render phase leaves 1,361,131 cycles (27.223 ms), but this remainder includes memory, other software and instrumentation; it is not a measured pure-arithmetic time. Source inspection shows explicit shift/add multiplication and software division in this path. Their individual shares have not yet been measured. Evaluate an integer multiplier or a validated resident GPU terrain path after identifying those shares, preserving source geometry and game behavior.
2. Keep FIFO-space reservation as an optional reproducible experiment. It measurably reduces command-cycle time but has not changed FPS. For a further bulk interface, first prototype a packed 32-bit MMIO enqueue feeding the existing byte decoder, with defined byte order, partial tails, free-space reservation and error semantics. The current byte-wide FIFO cannot accept four distinct byte writes per clock without a changed storage/serializer structure; resource and timing costs require fitting. Do not assume a fourfold end-to-end speedup.
3. Do not prioritize a larger FIFO based on these results: no waiting for FIFO capacity was observed. DMA/command-buffer work adds arbitration, memory ordering, buffer ownership and CRC handling. The entire currently timed command section is 5.884 ms in this view, and it includes CRC/packing as well as stores; that interval is not a DMA savings prediction. Prefer a bounded packed-MMIO experiment over a DMA redesign if further transport work is selected.
4. Cache-hit latency still matters to update/collision, where memory freezes are a large fraction, but the measured render freeze span is only 0.878 ms. Smaller-line measurements already favored the existing 32-byte default. Cache redesign is therefore secondary to identifying CPU render arithmetic in this workload.
5. Defer superscalar execution. Render has many redirects and source-level dependent arithmetic loops; wider issue would require evidence of independent instructions, new register-file/bypass/dependency logic and fitted timing. Presentation polling must not be used to justify widening the CPU.

Original FPGA SHA-256 b9386eb9aad671dff8313ca61a22b6e04874dc22ab1e94f42c2732790576b4ce and original Mario were restored and advanced frames successfully. Counter image SHA-256 is 6744adf087bea5139d0170b69e4ca4c1461efe275036333c3f446e65b2c15888. Profiling requires programming the counter-enabled image; optional builds do not overwrite the baseline packages. No hardware transport redesign was implemented, and existing rendering/collision issues are not claimed fixed.

Resume-safe wording: "Instrumented an RV32I FPGA SoC with physical retirement/stall counters and atomic CPU/GPU frame profiles; identified CPU rendering work rather than FIFO backpressure and reduced command-submission cycles by 8.13% in a fixed castle view using software FIFO reservations, with no measured frame-rate improvement."

