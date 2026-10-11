from pathlib import Path
import json,statistics,re
out=Path('build/arch-stage2b');results={}
for label in ('packed-normal','dma-normal','dma-local-normal','packed-detail','dma-detail','dma-local-detail'):
 r=json.loads((out/('physical-'+label+'.json')).read_text())
 if r.get('failure') or len(r['trials'])!=3:raise RuntimeError('Incomplete '+label)
 keys=r['trials'][0]['metrics'].keys()
 results[label]={'trials':[{'trial':t['trial'],'metrics':t['metrics'],'fps':t['observed_fps'],'position':t['position'],'render':t.get('phases',{}).get('render'),'dma':t.get('dma')} for t in r['trials']],
 'median':{k:statistics.median(t['metrics'][k] for t in r['trials']) for k in keys if k not in ('frame','cpu_abi')},'fps_median':statistics.median(t['observed_fps'] for t in r['trials'])}
base=results['packed-normal']['median']['game_cpu_cycles']
for label in ('dma-normal','dma-local-normal'):results[label]['ordinary_cpu_regression_percent']=(results[label]['median']['game_cpu_cycles']/base-1)*100
summary={'date':'2026-10-11','baseline_commit':'df9c539','hardware_implementation_commit':'59a4d3a','local_staging_commit':'40e4ee1','clock_hz':50000000,'scope':'Three standing spawn trials for each of six cases, all on one final DMA candidate image. Ordinary live timers are non-atomic; profiles are instrumented atomic completed-frame snapshots. No game FPS improvement or complete-level acceptance claim.',
 'measurements':results,'resources':{'stage2a_logic_elements':22675,'candidate_logic_elements':23788,'delta_logic_elements':1113,'stage2a_logical_memory_bits':2659684,'candidate_logical_memory_bits':2659688,'delta_logical_memory_bits':4,'m9k_blocks':354,'multipliers_9bit':80,'plls':2,'worst_setup_ns':.401,'worst_hold_ns':.086,'unconstrained_setup_hold':0},
 'decision':'Do not promote DMA: final command-local staging regresses ordinary CPU update+render by 8.52018%; retain experimental backend, restore Stage 2A packed Mario.'}
(out/'measurements.json').write_text(json.dumps(summary,indent=2)+'\n')
rows=[]
for label,title in [('packed-normal','Packed control'),('dma-normal','Global-state DMA'),('dma-local-normal','Command-local DMA')]:
 rs=results[label];vals=[t['metrics']['game_cpu_cycles'] for t in rs['trials']];med=rs['median']['game_cpu_cycles'];rows.append(f"| {title} | {', '.join(f'{v:,}' for v in vals)} | {med:,} | {med/50000:.5f} | {(med/base-1)*100:+.3f}% | {rs['fps_median']:.2f} |")
phase=[]
for label,title in [('packed-detail','Packed'),('dma-detail','Global-state DMA'),('dma-local-detail','Command-local DMA')]:
 rs=results[label];ts=rs['trials'];render={k:statistics.median(t['render'][k] for t in ts) for k in ts[0]['render']};phase.append(f"| {title} | {rs['median']['command_cycles']:,} | {render['cycles']:,} | {render['retired']:,} | {render['memory_freezes']:,} | {render['dependency_bubbles']:,} | {rs['median']['fifo_wait_span_cycles']:,} |")
text='''# ARCH-UPGRADE-001 Stage 2B: measured command DMA experiment

**Implemented and verified, but not promoted.** Buffer staging measurements justified testing DMA; the integrated 1 KiB double-buffered driver regresses ordinary standing-view CPU update-plus-render time by **8.520%** versus packed submission. Normal packed Mario and the accepted Stage 2A FPGA image are restored. This report preserves the unsuccessful first driver and the narrower software correction, rather than reporting the staging probe as game speedup.

Measured October 11, 2026. Reference commit df9c539 preserves the Stage 2A staging probe; hardware/interface implementation 59a4d3a; command-local staging 40e4ee1. Clocks, models, collision, gameplay, camera and original asset bytes are unchanged. Every game case uses the same 883,124-byte SDRAM asset image, SHA-256 afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6.

## Staging gate and implemented architecture

The [three-trial staging measurement](command-buffer-staging.md) compares actual packed submission to continuous RAM/SDRAM serialization on unchanged Stage 2A hardware. The 6,050-byte view takes 267,233 packed versus 193,692 SDRAM-staging cycles (5.34466 versus 3.87384 ms at 50 MHz). Six larger streams show 20.6-34.5% less CPU staging time; a 278-byte stream saves only 363 cycles. Each staged result passes independent full-byte/hash validation. These measurements exclude DMA reads, arbitration, stream publication and GPU drain; packed submission can include GPU backpressure.

Stage 2B therefore tests a reusable read-only SDRAM master feeding the existing GPU FIFO. It collects eight-word bursts, emits exact bytes under backpressure, validates source/length bounds, completes with a submission ID, and drains accepted bursts on loader cancellation. A transaction-owned round-robin arbiter separates CPU/cache and DMA responses without changing the controller/cache implementations. CPU write-through acknowledgement precedes descriptor publication. Two owned 1 KiB buffers preserve some CPU/GPU overlap; this size is an initial candidate, not a proven optimum. Packages reserve both buffers and require the advertised DMA capability before loader BEGIN.

The first driver persisted staging state for every byte. Disassembly showed additional state traffic; the software correction holds command state locally and persists it at command/buffer boundaries. Both versions preserve CRC, command boundaries and tails. [Register ABI, ownership, errors, cancellation and commands](gpu-command-dma.md) explain the complete implementation. CPU ISA, raster arithmetic, renderer pipeline and presentation cadence were not changed. No descriptor queue or write DMA was added.

## Ordinary physical game comparison

Three trials per case run on the **same final Stage 2B candidate SOF**, SHA-256 bbd6de457af231bef65b77771b5310dd2d2363a7b3aa2d7d6bb89329f90a4140. Every case uploads and verifies all immutable assets in trial 1, verifies CPU images on every trial, and restores packed Mario between cases. All standing positions are (-1328,260,4664). There is no external concurrent control sender in this measurement harness.

The existing ordinary live timer spans update plus render. Values are read from CPU RAM after loader hold and are non-atomic; they are not a render-only/frame-latency distribution:

| Firmware | All three CPU cycle samples | Median cycles | Median ms | Change vs packed | Median observed FPS |
| --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(rows)+'''

The local-state correction reduces the first DMA driver's median by 4,345 cycles (0.440%), but remains 77,131 cycles (1.54262 ms) slower than packed. It does not justify promotion. The prior Stage 2A ordinary packed median was also 905,274 cycles; the candidate-image packed median matches it, with one sample 62 cycles higher. This is a narrow standing control, not proof that arbitration has zero cost in other workloads.

Median ordinary update-through-present wall time is 1,668,299 cycles for packed and command-local DMA. Presentation waits rise when CPU work finishes earlier and shrink when CPU work finishes later; game tick and VGA page cadence constrain observed FPS near 30. Neither candidate improves measured FPS. No power or maximum-frequency claim is made.

## Instrumented diagnostics: locate the added cost

Three completed-frame snapshots per case, in CPU cycles. These builds materially perturb execution and must not replace the ordinary results:

| Firmware | Command span | Render phase | Retired render instructions | Memory freezes | Dependency bubbles | Historical FIFO wait field |
| --- | --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(phase)+'''

All snapshots serialize 7,011 bytes in 242 commands. Final command-local DMA retires 33,593 additional render instructions and spends 19,402 additional cycles frozen for memory versus packed; the first driver adds 57,438 retired instructions and 19,353 freezes. The correction reduces retirement but also changes dependency/redirect behavior, so the measured wall benefit is small. Staging bookkeeping, serialization and acknowledged SDRAM stores remain more expensive overall. These results do not isolate the exact cost of every staging instruction or CRC operation.

Final DMA counters: 7,011 accepted bytes and 1,760 response words per frame; request-grant waits 57,57,50 cycles; FIFO-publication waits 910,910,909 cycles. Rounded reads cover 7,040 bytes, with 29 extra tail bytes read but not published. Grant/FIFO waiting is small in this standing view and is not the main observed regression. DMA does not eliminate CPU CRC computation. The historical fifo_wait_span_cycles field is 1,279 for final DMA and 0 for packed; in DMA builds it means **buffer ownership checks/waits**, including check overhead, rather than FIFO-full time alone. DMA work overlaps CPU/GPU work, so these counters and nested command spans cannot be summed into serial frame time.

## Hardware fit and timing

| Metric | Accepted Stage 2A | Final Stage 2B | Difference |
| --- | --- | --- | --- |
| Logic elements | 22,675 | 23,788 | +1,113 |
| Logical memory bits | 2,659,684 | 2,659,688 | +4 |
| M9K blocks | 354 / 432 | 354 / 432 | 0 |
| Physical memory implementation bits | 3,262,464 | 3,262,464 | 0 |
| Embedded 9-bit multiplier elements | 80 | 80 | 0 |
| PLLs | 2 | 2 | 0 |
| Worst multicorner setup slack | +0.182 ns | +0.401 ns | Both pass |
| Worst multicorner hold slack | +0.126 ns | +0.086 ns | Both pass |

Setup/hold constraints report zero unconstrained clocks/input/output paths. Final worst setup is CLOCK_50; worst hold is fast-corner ENET0_RX_CLK. Changes in fitted slack are not a clock-speed improvement measurement.

The first fit used 23,611 logic elements but failed setup by 0.507 ns on the opposite-edge MMIO length-to-DMA descriptor-validation path. It was **never assembled or programmed**. Registering descriptor capture and validating on a full-cycle path adds one descriptor cycle and passes the unchanged constraints. Failed fit reports/source and final reports are preserved separately. The final image alone is used for all six physical comparison cases; the software correction does not change hardware.

## Correctness and remaining scope

Twenty-three host tests pass, including actual C-driver CRC/byte/tail equivalence, all payload lengths 0..255, randomized multi-command buffer crossings, feature rejection before submission, stale descriptor-error recovery, overlapping-buffer rejection and legacy/packed compatibility. Nine affected RTL regressions pass. The DMA test additionally covers 65,535/65,536-byte descriptors. Real controller/device simulation covers CPU write-through publication, row crossing, cache contention, exact FIFO ordering, illegal CPU enqueue during ownership, loader restart and response drain. Existing memory, packed FIFO, loader and MUL tests pass. Normal and detailed game builds pass specialized-C and ISA audits.

Seven castle terrain frames (1,573 ordered triangles), two Quake static views and eight authored fixtures match preserved full color/depth/palette and ordered triangle captures exactly through the final DMA engine. The native final-driver tests establish unchanged serialized bytes; the hardware is unchanged by the command-local software correction. These replays exclude full animated actors and mission/area transition behavior. Physical normal/detailed trials show startup, transfer and continued frame progress, but do not capture physical framebuffers or establish full-level traversal/collision acceptance. No movement speedup is claimed.

## Decision and follow-up

Retain --dma-gfx as an experimental generic backend; retain packed submission as the selected game transport. Global build firmware defaults remain unchanged. The physical FPGA is rolled back to Stage 2A SOF 917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32 and normal packed CPU image 4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda, with full upload/readback and advancing-frame validation recorded in final-running-check.json.

Do not add more DMA lanes, descriptor queues or larger buffers on the assumption that transfer bandwidth is limiting. A future staging experiment should measure a word/span serializer with fewer per-byte state/branch operations and less staging-store cost. Compare against packed on ordinary game workloads before changing hardware. Stage 3 setup/raster overlap remains an independent proposed measurement; Stage 0 actor/transition/physical-route coverage and Stage 1 admission/residency economics remain open.

Defensible resume wording: "Designed and verified a read-only SDRAM command DMA backend for an FPGA CPU/GPU SoC, including transaction arbitration, owned buffers and loader cancellation; validated exact renders and documented timing/resources, then rejected default deployment after an 8.52% measured CPU regression." No positive DMA performance claim is supported.

## Reproduce and evidence

Use the commands in gpu-command-dma.md for firmware, native tests and RTL validation. Raw [all physical samples and summaries](benchmarks/arch-upgrade-001-stage-2b/measurements.json) and [artifact hashes, build helpers, reports, captures and source snapshots](benchmarks/arch-upgrade-001-stage-2b/manifest.json) preserve all attempts. Local build helpers build_arch_stage2b.py, measure_arch_stage2b.py and measure_arch_stage2b_local.py are archived there. Generated game assets and SOF binaries remain local, with hashes; re-create packages from the original game-project pipeline. Full render replays share build/render-replay and must run serially. Physical measurements require one board/socket owner. Checkout the preserved commits in an isolated checkout for comparison rather than overwriting current work.
'''
Path('docs/architecture-stage-2b.md').write_text(text)
print('ordinary final regression',results['dma-local-normal']['ordinary_cpu_regression_percent'])
