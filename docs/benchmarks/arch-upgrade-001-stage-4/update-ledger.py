from pathlib import Path
p=Path('docs/architecture-upgrade-plan.md');s=p.read_text(encoding='utf-8');s=s.replace('Stage 3 optional upgrade verified and measured', 'Stage 3 optional upgrade verified and measured; Stage 4 optional two-lane upgrade accepted and selected')
s=s.replace('Optional upgrade accepted; selected Stage 3 image with normal packed Mario', 'Optional upgrade accepted; Stage 3 rollback preserved').replace('preserve this baseline for Stage 4', 'Stage 4 comparison completed; preserve this rollback')
s=s.replace('| 4: two pixel lanes | Not started | None | Validate banking and hazard model before lane duplication |', '| 4: two pixel lanes | Optional upgrade accepted; two lanes selected with normal packed Mario | Baseline 8082afd; implementation b465b03 / 721fada; [results](architecture-stage-4.md) | 17 exact replay frames; largest synthetic probe saves 49.3% before swap wait including parallel clear; ordinary CPU/FPS unchanged; +396 LEs / +12 M9Ks |')
s=s.replace('Stage 3 now adds optional setup/raster overlap with normal packed Mario.', 'Stage 3 adds optional setup/raster overlap; selected Stage 4 now adds adjacent-pixel lanes and parity-banked depth/color RAM with normal packed Mario.')
s=s.replace('preserve the measured Stage 3 control/candidate artifacts before Stage 4 banking/lane work.', 'preserve the measured Stage 3 rollback and Stage 4 control/candidate artifacts. Stage 4 improves measured GPU spans while ordinary standing CPU time and FPS remain unchanged; reassess CPU work and cadence before duplicating more lanes.')
p.write_text(s,encoding='utf-8')
p=Path('docs/hardware-improvement-record.md');s=p.read_text(encoding='utf-8');s+='''
## GPU-PIXEL-001: two adjacent pixel lanes and parity-banked RAM

October 11, 2026. ARCH-UPGRADE-001 Stage 4. Baseline 8082afd preserves accepted
Stage 3 commit 0a6434b; implementation b465b03 and compatibility/measurement
integration 721fada. Same 50 MHz CPU/GPU clocks, packed commands, game binaries
and assets; experimental command DMA remains disabled.

The two lanes retain ordered triangles, original signed arithmetic/depth clamp,
strict depth comparison and drain. Parity banks provide independent depth/color
access, explicit depth read/write forwarding and parallel clear. VGA read parity
and validity preserve latency and page ownership. Counters count pixels.

Fifteen affected RTL tests and six host tests pass. Exact color/depth/palette,
submitted triangles and seven event counters match 17 castle/Quake/boundary
replay frames. Real RAM tests include asynchronous display parity and explicit
forwarding. Eighteen physical reset trials cover resident-mesh probes, ordinary
standing Mario and instrumented standing Mario on each image. Raw trials,
source/configuration hashes, timing/resources and failures are archived.

Three identical repeats of the 128-face 65x65 resident-mesh probe reduce work
before swap waiting from 618,228 to 313,588 cycles (49.276% less): 38,400 cycles
saved by parallel clear and 266,240 additional cycles, matching raster-busy
reduction. Clear halves from 76,800 to 38,400 cycles. Tiny-probe savings are
almost entirely clear. Matched instrumented frame 251 retains the same seven
event counts while raster busy falls 272,307 to 142,504 cycles. These activity
spans overlap other work and cannot be summed into serial frame time.

Ordinary standing CPU update/render median is identical at 905,274 cycles;
observed FPS remains near 30. No ordinary CPU, complete-game FPS, power or Fmax
improvement is claimed. Fitted cost against matched control is +396 LEs
(23,789 to 24,185), +12 M9Ks (354 to 366 of 432), unchanged 2,659,684 logical
memory bits, 80 embedded 9-bit multipliers and two PLLs. Worst candidate setup/
hold slack is +0.623/+0.105 ns, with zero unconstrained setup/hold clocks and
input/output paths. Both variants pass the reported timing checks.

Stage 4 is selected as an optional reusable upgrade with normal packed Mario;
single-lane fallback and exact Stage 3 rollback remain available. Full firmware/
assets upload/readback and frame progression passed. Selected SOF hash:
52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235.
This is not full actor/transition or physical framebuffer acceptance.

Resume-safe claim: designed and verified a two-lane ordered FPGA rasterizer with
parity-banked depth/color RAM and explicit hazard forwarding; preserved exact
output across 17 replay frames and measured 49.3% less GPU work before swap
waiting in a specified resident-mesh benchmark, including parallel clear, at
+396 logic elements and +12 M9Ks. No ordinary Mario FPS gain is supported.
[Full results and reproduction](architecture-stage-4.md),
[measurements](benchmarks/arch-upgrade-001-stage-4/measurements.json) and
[raw evidence/hashes](benchmarks/arch-upgrade-001-stage-4/manifest.json).
''';p.write_text(s,encoding='utf-8')
