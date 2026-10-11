from pathlib import Path
import json,statistics
r=json.loads(Path('build/arch-stage3/measurements.json').read_text())
def f(v):return f'{v:,.0f}'
text='''
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
'''
for label,key in [('Logic elements','logic_elements'),('Logical memory bits','memory_bits'),('Physical M9K blocks','m9k'),('Physical memory implementation bits','physical_memory_bits'),('Embedded 9-bit multiplier elements','multipliers_9bit'),('PLLs','plls')]:
 a=r['hardware']['serial'][key];b=r['hardware']['overlap'][key]
 text+=f'| {label} | {f(a)} | {f(b)} | {b-a:+,} |\n'
text+='| Worst setup slack | +0.641 ns | +0.311 ns | Both pass |\n| Worst hold slack | +0.117 ns | +0.089 ns | Both pass |\n'
text+='''
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
'''
for i,label in enumerate(('5 x 5','33 x 33','65 x 65')):
 a=r['physical']['serial']['probe'][i];b=r['physical']['overlap']['probe'][i]
 av=a['total_cycles']['median']-a['swap_wait_cycles']['median'];bv=b['total_cycles']['median']-b['swap_wait_cycles']['median']
 text+=f"| {label} | {f(a['raster_cycles']['median'])} / {f(b['raster_cycles']['median'])} | {f(av)} / {f(bv)} | {(bv/av-1)*100:+.5f}% |\n"
text+='''
The medium and large cases each save 4,824 cycles / 0.09648 ms before swap wait
at 50 MHz. Their raster-busy unions fall 4,697 cycles. The smallest case adds
256 raster-busy cycles and two cycles before swap wait: setup and traversal
cannot usefully overlap when the geometry producer is slower than both. Queue
handoff adds latency in this case. Presenting still waits for VGA; no uncapped
physical FPS claim is supported.

### Ordinary Mario and detailed diagnostics

'''
for mode in ('serial','overlap'):
 n=r['physical'][mode]['normal'];text+=f"{mode.capitalize()} ordinary update+render trials: **{' / '.join(str(v) for v in n['game_cpu_cycles']['trials'])} cycles**; median **{f(n['game_cpu_cycles']['median'])} cycles / {n['game_cpu_cycles']['median']/50000:.5f} ms**. Observed FPS: {' / '.join(f'{v:.3f}' for v in n['observed_fps']['trials'])}.\n\n"
text+='''
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
'''
for kind in ('castle','quake'):
 for fid,v in r['replays']['serial'][kind]['frames'].items():
  b=r['replays']['overlap'][kind]['frames'][fid]
  text+=f"| {kind} {fid} | {f(v['begin_to_swap_request'])} | {f(b['begin_to_swap_request'])} |\n"
text+='''
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
'''
p=Path('docs/architecture-stage-3.md');s=p.read_text();s=s.replace('Status: baseline recorded; implementation and acceptance pending.','Status: implemented, verified and measured; optional scheduling upgrade accepted. Global serial fallback retained.')
s=s.replace('Every board\ncomparison finishes by restoring the exact accepted Stage 2A image and normal\nMario','Every board\ncomparison finishes by restoring the exact accepted Stage 2A image and normal\nMario')
p.write_text(s+text,encoding='utf-8',newline='\n')
print('Report updated from raw measurements')
