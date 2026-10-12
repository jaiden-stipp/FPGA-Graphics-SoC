from pathlib import Path
p=Path('build/arch-stage5/write-report.py');s=p.read_text().replace(r'.\scripts\run.ps1',r'.\\scripts\\run.ps1');p.write_text(s)
p=Path('docs/architecture-stage-5.md');s=p.read_text(encoding='utf-8').replace('.\\scripts\nun.ps1','.\\scripts\\run.ps1');p.write_text(s,encoding='utf-8')
p=Path('docs/architecture-upgrade-plan.md');s=p.read_text(encoding='utf-8');s=s.replace('Stage 4 optional two-lane upgrade accepted and selected', 'Stage 4 optional two-lane upgrade accepted; Stage 5 optional geometry worker accepted and selected')
s=s.replace('Optional upgrade accepted; two lanes selected with normal packed Mario', 'Optional upgrade accepted; Stage 4 rollback preserved')
s=s.replace('| 5: optional math worker | Deferred | None | Select only from updated profiles |', '| 5: optional math worker | Geometry worker accepted and selected; skinning deferred | Baseline 40219cec; implementation b677581 / df0649df; [results](architecture-stage-5.md) | Standing CPU update/render improves 28.319%; transform/outcodes 82.410%; exact three complete actor/game stream and GPU replay frames; reassess remaining clipping/command cost |')
s=s.replace('selected Stage 4 now adds', 'Stage 4 adds').replace('Stage 4 improves measured GPU spans while ordinary standing CPU time and FPS remain unchanged; reassess CPU work and cadence before duplicating more lanes.', 'Stage 4 improves measured GPU spans; selected Stage 5 adds the shared geometry worker and improves ordinary standing CPU update/render 28.319%, with FPS still around 30. Preserve both rollbacks and reassess clipping/command costs and cadence before duplicating more lanes.')
p.write_text(s,encoding='utf-8')
p=Path('docs/hardware-improvement-record.md');s=p.read_text(encoding='utf-8');s+='''
## CPU-GEOMETRY-001: queued Q8 transform/outcode worker

October 11, 2026. ARCH-UPGRADE-001 Stage 5. Baseline 40219cec preserves Stage 4
commit e0d776c. Implementation b677581 / df0649df; reproducible complete-game
stream/profiling integration 765ecbe. Three parallel signed multipliers compute
the original low-32-bit dot products and six shared frustum outcodes, with
bounded input/result queues, configuration ownership, reset/abort safety and
registered FIFO read responses. CPU owns cached source reads and render scratch
copies; no new SDRAM master or cache-coherency path. Game models, collision,
camera, animation, 16-bit clipping fractions, GPU raster/transport and clocks
remain unchanged. Normal packages retain compatibility; offload is feature gated.

An independent 1,152-vertex oracle and the real CPU/MMIO adapter agree with the
production C transform/plane kernel. Three complete actor/game command streams
match through CPUs/cache/SDRAM, and composed GPU replays match color/depth/palette
and 1,332 submitted triangles. The equivalence fixture uses synthetic decoder
backpressure/immediate presentation acknowledgement and supplies no timing claim.
Physical evidence comprises 15 complete comparative reset trials plus three
exploratory probe resets with their printed timings preserved separately.

Ordinary standing Mario CPU update/render medians fall 905,274 to 648,906 cycles
(28.319% less, 18.10548 to 12.97812 ms at configured 50 MHz). Observed FPS remains
around 30; no uncapped FPS improvement is claimed. Detailed transform/outcode
scope medians fall 312,333 to 54,939 cycles (82.410% less), including configuration,
source reads, input writes, polling and result copies. Matched frame 251 retains
all seven GPU events; worker snapshot 252 is a separate actor pose. Paired
on-chip-data 128-vertex probes repeat 38,039 software versus 5,565 complete-adapter
cycles; these are synthetic costs, not SDRAM game-time savings.

Fitted cost is +2,372 LEs (24,185 to 26,557), +12 embedded 9-bit multiplier
elements (80 to 92), no extra M9Ks (366/432), +4 logical memory bits and no new
PLLs. Candidate setup/hold minima +0.424/+0.128 ns pass at unchanged clocks, with
zero unconstrained setup/hold clock/input/output paths. No power/Fmax gain is
claimed. Stage 5 is selected with normal worker-enabled packed Mario; full
CPU/assets readback and running frame progression pass. Stage 4 rollback remains.

Resume-safe claim: designed and verified a feature-gated queued FPGA geometry
accelerator preserving fixed-point transform/frustum semantics and measured a
28.3% reduction in ordinary standing-scene CPU update/render time, including
transfer overhead, with exact complete-game command/GPU replay validation.
This is not complete-level or physical-framebuffer acceptance.
[Architecture/results](architecture-stage-5.md),
[measurements](benchmarks/arch-upgrade-001-stage-5/measurements.json) and
[raw evidence/hashes](benchmarks/arch-upgrade-001-stage-5/manifest.json).
''';p.write_text(s,encoding='utf-8')
