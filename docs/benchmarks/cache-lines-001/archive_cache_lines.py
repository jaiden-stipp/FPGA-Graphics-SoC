from pathlib import Path

import hashlib,json,re,shutil,statistics,subprocess

root=Path.cwd();dst=root/'docs/benchmarks/cache-lines-001';dst.mkdir(exist_ok=True)

labels=('baseline32','candidate16','candidate8','candidate32')

reports={n:json.loads((root/'build/cache-lines'/f'{n}.json').read_text()) for n in labels}

for n,r in reports.items():

 assert len(r['samples'])==3 and 'failure' not in r and r['restored_status']['initialized'] and not r['restored_status']['held']

 assert r['probe']['probe_sha256']=='abd76a715481d3376fcbef7098601a1325b54669b106dad7e91136b25c9e29d2'

 for trial in r['samples']:

  for i,p in enumerate(trial['phases']):

   assert p['sum']==r['probe']['checksums'][i]

   assert p['fill_words']==p['misses']*(r['line_bytes']//4)

 def copy(p):shutil.copy2(p,dst/p.name)

 copy(root/'build/cache-lines'/f'{n}.json');copy(root/'build/cache-lines'/f'{n}-program.log')

for n in ('candidate8','candidate16','candidate32'):

 copy(root/'build/cache-lines'/f'{n}-game.json')

for p in (root/'build').glob('line-*.log'):copy(p)

for p in (root/'build').glob('line*-quartus-*.log'):copy(p)

for n in (8,16,32):

 prefix=f'CacheLine{n}SoC'

 copy(root/'build'/f'{prefix}.qsf.snapshot')

 for ext in ('fit.summary','sta.summary','map.summary'):

  shutil.copy2(root/f'build/quartus-line{n}'/f'{prefix}.{ext}',dst/f'line{n}.{ext}.txt')

for ext in ('fit.summary','sta.summary','map.summary'):

 shutil.copy2(root/'build/quartus-burst'/f'BurstSoC.{ext}',dst/f'baseline32.{ext}.txt')

for p in ('run_line_tests.py','run_line_cpu_sizes.py','run_line_boundary_tests.py','build_cache_lines.py','archive_cache_lines.py'):

 copy(root/'build'/p)

copy(root/'build/cache-lines/probe.json');copy(root/'build/cache-lines/probe.bin');copy(root/'build/cache-lines/cache_line_probe_config.h');copy(root/'build/cache-lines/probe.map')

for p in ['rtl/sdram_cache.sv','rtl/sdram_controller.sv','rtl/soc_memory.sv','rtl/soc_top.sv','rtl/boards/de2_115_soc_top.sv','sim/sdram_cache_tb.sv','sim/sdram_memory_tb.sv','sim/sdram_cpu_tb.sv','sim/sdram_device_model.sv','scripts/cache_line_probe.py','scripts/cache_line_measure.py','scripts/cache_line_game_sample.py','firmware/tests/cache_line_probe.c','firmware/src/player.c','firmware/src/world.c']:

 shutil.copy2(root/p,dst/(Path(p).name+'.txt'))

compiler=subprocess.check_output(['C:/Program Files/LLVM/bin/clang.exe','--version'],text=True);(dst/'compiler-version.txt').write_text(compiler)

def parse_resources(prefix):

 fit=(dst/(prefix+'.fit.summary.txt')).read_text();sta=(dst/(prefix+'.sta.summary.txt')).read_text()

 def value(name):return int(re.search(re.escape(name)+r'\s*:\s*([\d,]+)',fit)[1].replace(',',''))

 return {'logic_elements':value('Total logic elements'),'memory_bits':value('Total memory bits'),'dsp_9bit_elements':value('Embedded Multiplier 9-bit elements'),'plls':value('Total PLLs'),'clock50_setup_slack_ns':float(re.search(r"Model Setup 'CLOCK_50'\s*Slack\s*:\s*([-+\d.]+)",sta)[1]),'minimum_reported_slack_ns':min(float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',sta))}

resources={n:parse_resources('baseline32' if n=='baseline32' else 'line'+str(reports[n]['line_bytes'])) for n in labels}

metrics={}

for n,r in reports.items():

 metrics[n]=[]

 for i in range(6):

  phases=[s['phases'][i] for s in r['samples']]

  item={key:statistics.median([p[key] for p in phases]) for key in ('cycles','hits','misses','fill_words')}

  item['name']=phases[0]['name'];item['all_cycles']=[p['cycles'] for p in phases];item['fill_bytes']=4*item['fill_words'];item['hit_percent']=100*item['hits']/(item['hits']+item['misses'])

  item['cycle_change_percent']=100*(item['cycles']-statistics.median([s['phases'][i]['cycles'] for s in reports['baseline32']['samples']]))/statistics.median([s['phases'][i]['cycles'] for s in reports['baseline32']['samples']])

  metrics[n].append(item)

# The refactored default must preserve the original line-size behavior/counts.

for old,new in zip(metrics['baseline32'],metrics['candidate32']):

 for key in ('hits','misses','fill_words'):assert old[key]==new[key],(key,old,new)

 assert abs(old['cycles']-new['cycles'])<100,(old,new)

for size in (32,16,8):

 for tb in ('sdram_cache_tb','sdram_memory_tb'):

  for burst in (0,1):

   log=(dst/f'line-{size}-{tb}-burst{burst}.log').read_text();assert 'PASS '+tb in log and '** Fatal:' not in log

for size in (16,8):

 log=(dst/f'line-{size}-sdram_cpu_tb.log').read_text();assert 'PASS sdram_cpu_tb' in log and '** Fatal:' not in log

assert 'PASS sdram_cpu_tb' in (dst/'line-sdram_cpu_tb.log').read_text()

assert 'PASS udp_loader_tb' in (dst/'line-udp_loader_tb.log').read_text()

package=json.loads((root/'build/mario-castle-sdram-direct.package.json').read_text())

manifest={'experiment':'CACHE-LINES-001','date':'2026-10-10','board':'DE2-115 EP4CE115F29C7','clock_hz':50000000,'baseline_source_commit':subprocess.check_output(['git','rev-parse','b4616a3'],text=True).strip(),'candidate_rtl_commit':subprocess.check_output(['git','rev-parse','a75c02b'],text=True).strip(),'selected_line_bytes':32,'selected_sof_sha256':reports['candidate32']['sof_sha256'],'method':'Three sequential physical trials per bitstream; identical 3088-byte RV32I binary and castle assets, excluded eviction before each workload, immediate repeat passes. Three supplementary stationary Mario windows per candidate. No traversal-FPS or whole-game speedup claim.','probe':json.loads((dst/'probe.json').read_text()),'metrics':metrics,'resources':resources,'restored_package_segments':package['segments'],'model_limitation':'Sparse SDRAM model burst first-beat alignment was calibrated during BURST-001; BL2/4/8 have physical loader and probe verification, not an independent vendor timing-model qualification.'}

manifest['evidence_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dst.iterdir()) if p.is_file() and p.name!='measurements.json'}

(dst/'measurements.json').write_text(json.dumps(manifest,indent=2)+'\n')

lines=['# Equal-capacity cache-line comparison','', 'CACHE-LINES-001 — measured October 10, 2026 on the DE2-115 at 50 MHz.','', '**Decision: retain 32-byte lines as the default.** 16-byte lines offer a small collision-kernel benefit but slow geometry; 8-byte lines slow both castle kernels. Smaller lines remain selectable for other workloads.','', '## Controlled configurations','', '| Line bytes | Data capacity | Direct-mapped lines | SDRAM read burst | Tag bits per line |','|---:|---:|---:|---|---:|','| 32 | 4 KiB | 128 | BL8 | 15 |','| 16 | 4 KiB | 256 | BL4 | 15 |','| 8 | 4 KiB | 512 | BL2 | 15 |','', 'These are design settings, not measured performance. The data array, direct mapping, blocking completion, write-through/no-write-allocation policy, CPU ISA, GPU and game models stay the same. The number of tags/valid bits increases for smaller lines. MRS is 0x233/0x232/0x231 with CL3 and single-location writes. The refresh admission reserve tracks burst length (8/4/2 clocks). No prefetch, early restart, associativity or write-buffer change is included.','', '## Method and coverage','', 'One identical 3,088-byte RV32I probe ran three times per image. Its SHA-256 is `'+manifest['probe']['probe_sha256']+'`. Castle assets are identical in every test: `'+manifest['probe']['assets_sha256']+'`. CPU MMIO cycle counters include loop/arithmetic and refresh costs; hit/miss/fill counters are sampled as differences. Host code independently computes expected collision and geometry hashes from the packaged bytes; every trial must match, and fill words must equal misses × line words.','', '- Collision: the unchanged production `world_collision` and `player_floor` functions query an 8×8 lattice in each of five areas. A pass makes 320 queries, examines 2,104 floor candidates and finds 182 floor contacts. This includes empty-space queries and is a broad floor-query workload, not a recorded walking route or wall/jump test.','- Geometry: sequential CPU traversal of all chunks reads 8,259 original vertices and 8,278 triangle records, folding every coordinate/index/color. This measures mesh-data loading locality; it does not execute visibility, transforms, GPU rasterization or a complete frame.','- Sparse control: 64 distinct reads with a fixed 32-byte stride, followed by the same reads again. The addresses stay identical for all line sizes.','- Before each cold workload, reads from a separate 4 KiB eviction buffer replace every cache index; eviction cost is outside the measurement. The immediate repeat is measured separately. Collision and geometry span more than the cache, so “repeat” does not imply everything is warm. The sparse repeat is entirely hits.','', '## Physical cycle results','', 'Median of three trials; lower is better. Baseline is the original accepted BL8 bitstream. Percentages below are calculated from medians, not separate measurements.','', '| Workload | Original 32 B | 16 B | Change | 8 B | Change | Rebuilt 32 B |','|---|---:|---:|---:|---:|---:|---:|']

for i in range(6):

 a,b,c,d=(metrics[n][i] for n in labels)

 lines.append(f"| {a['name']} | {a['cycles']:,.0f} | {b['cycles']:,.0f} | {b['cycle_change_percent']:+.3f}% | {c['cycles']:,.0f} | {c['cycle_change_percent']:+.3f}% | {d['cycles']:,.0f} |")

lines+=['','Every individual trial and checksum is preserved in the raw JSON files; ranges are not discarded. All four images passed all checksums. The rebuilt 32-byte configuration has the same hit/miss/fill counts as the original image and cycle counts consistent with the variation across repeated trials.','', '## Misses and fill traffic','', 'Cold pass counters below. Fill bytes = measured fill words × 4. This measures SDRAM data traffic; it does not prove that each unrequested neighboring word was unused later.','', '| Workload | Line bytes | Read hits | Read misses | Fill words | Fill bytes |','|---|---:|---:|---:|---:|---:|']

for i in (0,2,4):

 for n in labels[:3]:

  p=metrics[n][i];size=reports[n]['line_bytes'];lines.append(f"| {p['name']} | {size} | {p['hits']:,.0f} | {p['misses']:,.0f} | {p['fill_words']:,.0f} | {p['fill_bytes']:,.0f} |")

lines+=['', 'The collision workload fetches fewer words with smaller lines, but misses more often. The production collision kernel also performs substantial arithmetic and control work. Reduced fill traffic produces very little total-cycle benefit at 16 bytes and a regression at 8 bytes; traffic reduction alone is not a speedup measurement. Geometry fill traffic changes little while miss count rises sharply; each miss repeats SDRAM activation/CAS/recovery overhead. This explains why the larger line wins geometry even though its isolated miss takes longer.','', '## Fitted resources and timing','', 'Measured whole-SoC Quartus Lite 18.1 Build 625 summaries; every image passed all reported timing summaries at the existing clocks. Placement/routing changes in slack are not a maximum-frequency measurement.','', '| Image | Logic elements | Memory bits | 9-bit DSP elements | PLLs | CLOCK_50 setup slack ns | Min reported slack ns |','|---|---:|---:|---:|---:|---:|---:|']

for n in labels:

 r=resources[n];lines.append(f"| {n} | {r['logic_elements']:,} | {r['memory_bits']:,} | {r['dsp_9bit_elements']} | {r['plls']} | {r['clock50_setup_slack_ns']:.3f} | {r['minimum_reported_slack_ns']:.3f} |")

lines+=['','## Simulation and correctness','', '| Line bytes | Burst cold read cycles | Hit cycles | Loader bypass read cycles | BL1 cold fill cycles |','|---:|---:|---:|---:|---:|','| 32 | 19 | 3 | 22 | 107 |','| 16 | 15 | 3 | 18 | 55 |','| 8 | 13 | 3 | 16 | 29 |','', 'These are actual controller/bridge/device-model simulation results, not board latency measurements. Each burst miss uses one READ; BL1 fills use 8/4/2 READs. Cache and controller tests passed all three sizes in burst and BL1 modes, including every critical-word offset at row/bank ends, all address lines, signed byte/half loads, masked stores, refresh, conflicts, no write allocation, loader bypass, and in-flight/last-beat invalidation. Real RV32I self-tests passed at every size with pipeline holding and no duplicate retirement. UDP-loader protocol/readback tests passed. The cache-disabled 8-byte-parameter control retains 13-cycle single-word reads and loader reads. The sparse SDRAM model retains the earlier physical first-beat calibration; this is not independent vendor-model timing qualification.','', 'On each physical image, the full assets and temporary eviction buffer were uploaded/readback-verified before the probe. After measurement, the complete original Mario CPU and assets package was uploaded/readback-verified again and completed frames. This verifies data loading and execution; no automated visual traversal/collision regression claim is made. Existing depth/rendering issues are outside this experiment.','', '## Supplementary standing Mario observations','', 'Three windows per candidate, each with 12 status samples separated by 0.25 seconds. Each window records actual elapsed time and completed-frame delta. Player position was checked after each window; all were (-1328, 260, 4664). Camera/input were not scripted, so these are supplementary observations, not a controlled traversal benchmark. Frame-counter quantization over about 2.75 seconds limits resolution; tiny FPS differences are not evidence of a gain. CPU/stage globals are last-published/partial-next-frame snapshots and must not be added to infer frame time.','', '| Image | Individual observed FPS |','|---|---|']

for n in ('candidate32','candidate16','candidate8'):

 g=json.loads((dst/f'{n}-game.json').read_text());assert all(w['position_u32']==[4294965968,260,4664] for w in g['windows'])

 lines.append('| '+n+' | '+', '.join(f"{w['observed_fps']:.3f}" for w in g['windows'])+' |')

lines+=['', 'The standing view remains about 20 FPS across sizes. This experiment does not establish a game-FPS improvement.','', '## Selection and reuse','', 'Retain 32 bytes: geometry is fastest, collision nearly ties 16 bytes, and tag/valid overhead is lowest. 16 bytes remains useful to try for a measured collision-heavy workload; 8 bytes benefits truly sparse reads but loses both tested castle kernels. No unmeasured game-frequency weighting is used to invent an overall speedup. A traversal replay with input/camera control would be needed to choose differently for a specific complete game.','', 'Generate a selected configuration with `python scripts/soc.py quartus-project --cache-line-bytes 16` (or 8/32). `--disable-burst` still compares BL1 filling without changing the selected cache line or total capacity. Generation does not build or program hardware.','', 'From the repository root, on the recorded Windows LLVM/Quartus/ModelSim setup, reproduce the experiment after recreating the same castle direct package:','', '```powershell','python scripts/soc.py portable-game --project build/castle/game.project.json --terrain-direct','python scripts/cache_line_probe.py','python docs/benchmarks/cache-lines-001/run_line_tests.py','python docs/benchmarks/cache-lines-001/build_cache_lines.py','python scripts/cache_line_measure.py --size 32 --sof build/quartus-burst/BurstSoC.sof --label baseline32','python scripts/cache_line_measure.py --size 8 --sof build/quartus-line8/CacheLine8SoC.sof --label candidate8','python scripts/cache_line_game_sample.py --size 8 --label candidate8','python scripts/cache_line_measure.py --size 16 --sof build/quartus-line16/CacheLine16SoC.sof --label candidate16','python scripts/cache_line_game_sample.py --size 16 --label candidate16','python scripts/cache_line_measure.py --size 32 --sof build/quartus-line32/CacheLine32SoC.sof --label candidate32','python scripts/cache_line_game_sample.py --size 32 --label candidate32','```','', 'The build helper uses the preserved QSF template, separate outputs and checks timing before assembly. Test/measurement scripts use local tool paths; edit tool locations when reproducing on another host. The probe builder derives the area address/count from the newly packaged assets and recomputes golden hashes; any changed package is a new experiment. The physical runner verifies the original baseline hash or candidate timing summary, checks data/counter results and restores Mario in `finally`; on measurement failure it first restores the proven BL8 bitstream. Reproduction requires locally supplied game assets and the prior baseline SOF; neither is committed as game data.','', '## Preserved references','', '- Original source: `'+manifest['baseline_source_commit']+'`.','- Candidate RTL/probe source: `'+manifest['candidate_rtl_commit']+'`.','- Baseline and candidate SOFs remain in separate ignored build directories; exact hashes and all raw trial values are in [measurements.json](benchmarks/cache-lines-001/measurements.json).','- [Raw evidence directory](benchmarks/cache-lines-001/) contains simulation logs, QSF snapshots, Quartus summaries/logs, compiler version, own probe binary/config/map, physical trial JSON and source snapshots; game assets are referenced only by hashes.','- Selected FPGA image SHA-256: `'+manifest['selected_sof_sha256']+'`. Mario is restored on this 32-byte image.','', 'Resume-safe statement: “Benchmarked equal-capacity BL2/BL4/BL8 SDRAM cache fills on an RV32I FPGA SoC with production collision queries and original mesh-data traversal, and retained 32-byte lines based on measured locality/resource tradeoffs.” Do not claim that shrinking lines improved game FPS.','']

(root/'docs/cache-line-comparison.md').write_text('\n'.join(lines),encoding='utf-8')

record=root/'docs/hardware-improvement-record.md';text=record.read_text(encoding="utf-8");marker='## CACHE-LINES-001: equal-capacity line-size comparison'

if marker not in text:

 text+='\n'+marker+'\n\nMeasured October 10, 2026: tested 8-, 16- and 32-byte lines at 4 KiB data capacity on the physical DE2-115, with one identical RV32I probe and castle asset package, three trials per image. Retained 32-byte lines: 16-byte lines slightly improve floor-query time but slow mesh-data traversal; 8-byte lines lose both castle kernels while improving a sparse control. All data checksums/readback and timing checks pass. Standing Mario remains approximately 20 FPS; no traversal-FPS gain is established.\n\nSee [full comparison and evidence](cache-line-comparison.md) for absolute cycles, miss/fill traffic, every trial, resource/timing reports, source/artifact hashes, workload coverage and limitations. The source baseline and experimental implementation are separate commits.\n'

 record.write_text(text,encoding="utf-8")

print(json.dumps({'metrics':metrics,'resources':resources,'selected_sha256':manifest['selected_sof_sha256']},indent=2))

