from pathlib import Path
p=Path('docs/architecture-upgrade-plan.md');s=p.read_text()
s=s.replace('Stage 2A verified and measured; Stage 2B deferred','Stage 2A accepted; Stage 2B experimental/not promoted; Stage 3 optional upgrade verified and measured')
s=s.replace('| 3: overlapping setup | Not started | None | Compare setup idle cost and queue occupancy |','| 3: overlapping setup | Optional upgrade accepted; selected Stage 3 image with normal packed Mario | Baseline 6153efa; implementation 2bf56dd / 8bb928c; [results](architecture-stage-3.md) | Exact 17-frame replay match; medium resident-mesh work before swap wait improves 2.176%; ordinary CPU/FPS unchanged; preserve this baseline for Stage 4 |')
s=s.replace('The accepted Stage 2A image and normal packed Mario are restored. Keep DMA experimental;', 'Stage 2A remains the selected transport; Stage 3 now adds optional setup/raster overlap with normal packed Mario. Keep DMA experimental;')
s=s.replace('and measure Stage 3 setup/raster overlap independently.', 'and preserve the measured Stage 3 control/candidate artifacts before Stage 4 banking/lane work.')
p.write_text(s,encoding='utf-8',newline='\n')
p=Path('docs/hardware-improvement-record.md')
s=p.read_text()+'''

## GPU-SETUP-001 / ARCH-UPGRADE-001 Stage 3: overlapping setup and rasterization

Implemented and measured October 11, 2026. Baseline 6153efa; initial implementation
2bf56dd; Quartus compatibility correction 8bb928c. A selectable producer computes
setup/depth gradients while an ordered consumer rasterizes, with a stable two-record
queue and explicit busy/drain page-swap barrier. Existing arithmetic, strict depth
order, command ABI, models, gameplay, cache and clocks are preserved.

Seventeen complete captured terrain/fixture frames (seven castle, two Quake, eight
authored) match accepted color, depth, palette and ordered triangle references
exactly. Eleven affected RTL regressions and six existing host tests pass; reset
with queued/active work and full-queue stability are covered. Eighteen physical
trials cover serial and overlap images, resident-mesh GPU probes, ordinary standing
Mario and instrumented standing diagnostics. The measurement probe passes C-subset
and a 580-instruction RV32I audit. Coverage excludes whole-game actors/transitions,
physical framebuffer capture and full-level traversal acceptance.

A synthetic 128-face resident mesh with 33x33 projected bounds reduces GPU total
minus swap wait from 221,644 to 216,820 cycles (4.43288 to 4.33640 ms at 50 MHz,
2.17646% less work before swap waiting). The 65x65 case saves the same 4,824 cycles;
the 5x5 case adds two such cycles and 256 raster-busy cycles. These are synthetic
GPU scheduling results, not original-game FPS gains. Ordinary standing update+render
median is identical at 905,336 cycles in both images, with FPS near 30. Matched
instrumented frame 251 has identical seven event counts and geometry stalls falling
238,048 to 209,639; nested/overlapping spans are not summed as serial frame time.

Matched-control fitted cost: +1,010 logic elements (22,774 to 23,784), unchanged
2,659,684 logical memory bits, 354 M9Ks, 80 embedded 9-bit multiplier elements and
two PLLs. Candidate worst multicorner setup/hold slack is +0.311/+0.089 ns at
unchanged clocks, with zero unconstrained setup/hold clocks/input/output paths.
No maximum-frequency or power improvement is claimed. Initial tool failures and
both hardware hashes are retained. Serial stays the global fallback; Stage 3 is
accepted as an optional reusable scheduling upgrade. Stage 2B DMA stays disabled.

Resume-safe claim: designed and verified an ordered setup/raster overlap engine,
validated exact output across 17 replay frames and measured 2.176% lower GPU work
before swap waiting in a specified synthetic resident-mesh workload. No ordinary
Mario CPU or FPS improvement is supported. [Full results, contracts and reproduction]
(architecture-stage-3.md), [measurements](benchmarks/arch-upgrade-001-stage-3/measurements.json)
and [raw evidence/hashes](benchmarks/arch-upgrade-001-stage-3/manifest.json).
'''
s=s.replace('[Full results, contracts and reproduction]\n(architecture-stage-3.md)','[Full results, contracts and reproduction](architecture-stage-3.md)')
p.write_text(s,encoding='utf-8',newline='\n')
p=Path('.gitattributes');s=p.read_text()+'\ndocs/benchmarks/arch-upgrade-001-stage-3/** -text\n';p.write_text(s,encoding='utf-8',newline='\n')
