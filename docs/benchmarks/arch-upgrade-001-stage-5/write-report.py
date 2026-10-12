from pathlib import Path
import json
out=Path('build/arch-stage5');r=json.loads((out/'measurements.json').read_text());sel=json.loads((out/'accepted-running-check.json').read_text())
r['game_equivalence']=json.loads((out/'game-comparison.json').read_text());r['gpu_equivalence']=json.loads((out/'gpu-comparison.json').read_text())
r['scope']='Accepted optional geometry worker. Paired on-chip-data synthetic probe and three ordinary/detailed standing resets per hardware. Configuration/input/poll/output copies included. Exact three-frame real CPU/cache/SDRAM game command streams, including actors, with synthetic decoder backpressure/immediate presentation ack; composed GPU replays match color/depth/palette/triangles. Not full-level traversal or uncapped FPS/power/Fmax evidence.'
(out/'measurements.json').write_text(json.dumps(r,indent=2)+'\n')
a=r['hardware']['control'];b=r['hardware']['worker'];pa=r['physical']['control'];pb=r['physical']['worker']
vc=pa['detail_scopes']['vertex_transform_outcodes']['cycles']['median'];vw=pb['detail_scopes']['vertex_transform_outcodes']['cycles']['median']
text='''\n## Implemented architecture and reproduction

The generic worker performs three parallel signed products per coordinate axis,
registers their low 32 bits, accumulates at the original width, floors by an
arithmetic shift of eight, adds translation, and evaluates the existing planes.
Input/result FIFOs preserve vertex order and hold output under backpressure.
The descriptor remains active until every result is consumed; configuration
writes while active are rejected. Abort/reset discard work. Read data is
registered on the peripheral edge before the final word pops its FIFO entry,
matching the CPU's falling-edge RAM interface. The original combinational
response build was cancelled before deployment; the corrected interface passes
real CPU tests against the production C transform/plane functions.

`rtl/geometry_worker.sv` is selected by `SOC_GEOMETRY_WORKER`. CPU feature bit 1
and GW ABI 0x47570101 advertise it through MMIO and UDP status. Its page is separate
from existing graphics registers. `firmware/include/geometry_worker.h` streams
at most four outstanding vertices and copies results into the existing render
scratch buffer. `world.c` retains its original kernel when the capability is
absent. No game model, collision, camera, animation, clipping intersection,
GPU command layout, SDRAM master, cache policy or clock changes are introduced.
The v1 planes are the shared renderer's existing policy; other frustum policies
require an adapter or a versioned extension, not silent reinterpretation.

Normal packages remain compatible. `--geometry-offload` adds a versioned CPU
capability requirement checked before BEGIN, and a distinct package filename.
The mandatory specialized-C/ISA audits still target RV32I plus MUL only.
The candidate normal CPU binary is 26,848 bytes, versus 26,332 in control;
its 883,124-byte asset segment has the same baseline hash.

```powershell
.\\scripts\\run.ps1 geometry_vectors.py
.\\scripts\\run.ps1 build_geometry_probe.py
.\\scripts\\run.ps1 soc.py sim --simulator modelsim --geometry-worker `
  --tests geometry_worker_tb,cpu_geometry_tb
.\\scripts\\run.ps1 soc.py portable-game --project build/castle/game.project.json `
  --terrain-direct --packed-gfx --integer-mul --geometry-offload
# Add --profile-detail for the instrumented package.
.\\scripts\\run.ps1 build_geometry_worker.py both
# Run game equivalence/canonical GPU replay before normal gated profiling:
.\\scripts\\run.ps1 measure_geometry_worker.py
```

The optional `--pending-equivalence` measurement mode was used for provisional
profiling while the long CPU simulation ran. It automatically restores Stage 4;
promotion separately requires exact game/GPU output, fitted timing/coverage,
asset identity and measured ordinary CPU benefit. No provisional result was
selected before those checks passed.

## Verification and measured results

The independent wide-integer oracle covers 1,152 vertices in ten descriptors,
including signed rounding, wraparound and frustum boundaries. Queue tests cover
backpressure, count bounds, active configuration ownership, reset and abort.
The actual RV32I CPU/RAM/MMIO adapter agrees with the original production C
kernel on all probe inputs. The probe audits 467 instructions, with one static
MUL instruction and no unsupported M operations. Packed MMIO and SDRAM RTL
regressions also pass; 42 host tests cover shared-world/terrain behavior and
loader/transport capability gates.

Three complete standing game command streams match exactly through real CPUs,
caches and SDRAM, including actors. The fixture uses controlled decoder
backpressure and immediate presentation acknowledgement; it is not a timing/FPS
measurement. Replaying both streams through the unchanged Stage 4 GPU yields
identical color/depth/palette and 1,332 ordered submitted triangles across three
frames. A slower combined CPU+GPU simulation was abandoned and is retained
separately, never counted as a pass. This is not complete-level traversal or a
physical framebuffer comparison.

### Fitted resources and timing

| Metric | Control | Worker | Difference |
| --- | ---: | ---: | ---: |
'''
for label,key in [('Logic elements','logic_elements'),('Logical memory bits','memory_bits'),('M9Ks','m9k'),('Physical block-memory bits','physical_memory_bits'),('9-bit multiplier elements','multipliers_9bit'),('PLLs','plls')]:text+=f'| {label} | {a[key]:,} | {b[key]:,} | {b[key]-a[key]:+,} |\n'
for label,key in [('Worst setup slack (ns)','setup_min_ns'),('Worst hold slack (ns)','hold_min_ns')]:text+=f'| {label} | +{a[key]:.3f} | +{b[key]:.3f} | Both pass |\n'
text+='\nBoth images pass all reported timing checks at unchanged clocks, with zero\nunconstrained setup/hold clocks and input/output paths. No Fmax or power gain\nis claimed. Queues use fitted logic; M9Ks remain 366/432.\n\n### Physical ordinary standing game\n\n| Metric | Control trials | Worker trials |\n| --- | --- | --- |\n'
for label,key in [('CPU update/render cycles','game_cpu_cycles'),('Observed FPS','observed_fps')]:
 fmt=lambda v: ', '.join(f'{x:.3f}' if key=='observed_fps' else f'{int(x):,}' for x in v)
 text+=f"| {label} | {fmt(pa['normal'][key]['trials'])} | {fmt(pb['normal'][key]['trials'])} |\n"
x=pa['normal']['game_cpu_cycles']['median'];y=pb['normal']['game_cpu_cycles']['median']
text+=f'\nMedian CPU update/render falls {x:,} to {y:,} cycles: {(1-y/x)*100:.3f}%\nless, or {x/50000:.5f} to {y/50000:.5f} ms at configured 50 MHz. This is the\nordinary binary, not an instrumented estimate. Observed FPS stays around 30;\nuncapped FPS was not measured and gameplay cadence was not changed.\n\n'
text+='### Detailed profiles and paired kernel probe\n\n| Transform/outcode scope | Control | Worker |\n| --- | --- | --- |\n'
for label,key in [('Cycles','cycles'),('Calls','calls')]:text+=f"| {label} | {pa['detail_scopes']['vertex_transform_outcodes'][key]['trials']} | {pb['detail_scopes']['vertex_transform_outcodes'][key]['trials']} |\n"
text+=f'\nScope medians are {vc:,} and {vw:,} cycles ({(1-vw/vc)*100:.3f}% less), including\nconfiguration, source reads, input writes, polling and returned-result copies.\nDetailed control frame IDs are {pa["detail"]["frame_ids"]}; worker IDs are\n{pb["detail"]["frame_ids"]}. Matched frame 251 preserves all seven GPU events:\n444 submitted, 4 clipped, 195 culled, 263,013 bounding-box pixels, 90,955 inside,\n5,999 rejected and 84,956 written. Worker frame 252 has a different actor pose\nand is preserved separately, not treated as a matched frame-251 comparison.\nInstrumented timings are not substituted for ordinary CPU time.\n\n'
text+='The same candidate CPU also measures the original kernel and complete adapter\nusing static on-chip vertices. All three complete probe repeats are identical:\n\n| Vertices in descriptor | Original kernel cycles | Adapter cycles |\n| --- | ---: | ---: |\n'
for i,n in enumerate([1,127,128]):
 p=r['paired_probe'][i];text+=f"| {n} | {p['software_cycles']['median']:,} | {p['adapter_cycles']['median']:,} |\n"
text+='\nThe other seven 128-vertex descriptors also report 38,039 / 5,565 cycles.\nThese are synthetic on-chip-data costs, not SDRAM game-frame savings. There are\n15 complete raw comparative trials (3 paired probes plus 3 ordinary and 3\ndetailed resets per hardware). Three earlier exploratory probe resets have\nprinted timing pairs and restoration logs preserved separately; their unprinted\ncounters/status were not reconstructed.\n\n## Selection, artifacts and limits\n\n'
text+=f"Stage 5 is accepted as an optional shared geometry upgrade. Selected SOF:\n`{sel['sof']}`, SHA256 `{sel['sof_sha256']}`.\nNormal worker-enabled packed Mario is loaded. CPU/assets upload and readback\npassed; initialized/released CPU frames advance {sel['first_status']['scratch']} to {sel['last_status']['scratch']} over one second,\nwith CPU feature bit 1 set and GPU features 3. Exact Stage 4 restoration was\nverified after both exploratory and comparative measurements.\n\n"
text+='Retain Stage 4 as rollback. The next reassessment should use the remaining\nclipping and command costs; do not infer an uncapped FPS, power, complete-game\nor maximum-frequency improvement from this standing-view CPU reduction.\n\n[Measurements](benchmarks/arch-upgrade-001-stage-5/measurements.json),\n[raw evidence/hash manifest](benchmarks/arch-upgrade-001-stage-5/manifest.json)\nand [source provenance](benchmarks/arch-upgrade-001-stage-5/provenance.json).\n'
p=Path('docs/architecture-stage-5.md');s=p.read_text(encoding='utf-8');s=s.replace('No Stage\n5 performance improvement or deployment is claimed yet.', 'Results and selection follow below; the baseline contract above was committed\nbefore hardware edits.')
s=s.split('\n## Implemented architecture and reproduction\n')[0]+text
s=s.replace('# ARCH-UPGRADE-001 Stage 5: optional queued geometry worker\n', '# ARCH-UPGRADE-001 Stage 5: optional queued geometry worker\n\nImplemented, verified and selected. Ordinary standing Mario CPU update/render\nmedian improves 28.319%; observed FPS remains around 30.\n')
p.write_text(s,encoding='utf-8')
