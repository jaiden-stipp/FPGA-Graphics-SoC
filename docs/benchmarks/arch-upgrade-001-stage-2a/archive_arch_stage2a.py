from pathlib import Path
import hashlib,json,shutil,statistics,re,zipfile
root=Path.cwd();run=Path('build/arch-stage2a');dest=Path('docs/benchmarks/arch-upgrade-001-stage-2a');dest.mkdir(parents=True,exist_ok=True)
def copy(p,name=None):
 p=Path(p)
 if p.is_file():shutil.copyfile(p,dest/(name or p.name))
for p in run.glob('*'):
 if p.is_file() and p.suffix in ('.log','.json','.qsf'):copy(p)
for suffix in ('fit.summary','sta.summary','fit.rpt','sta.rpt'):copy('build/quartus-arch-stage2a/ArchStage2ASoC.'+suffix,'candidate-'+suffix)
for p in (run/'attempt-1-status-preflight').glob('*'):
 if p.is_file() and p.suffix!='.sof':
  d=dest/'attempt-1-status-preflight';d.mkdir(exist_ok=True);shutil.copyfile(p,d/p.name)
for name in ('build_arch_stage2a.py','measure_arch_stage2a.py','deploy_arch_stage2a.py','archive_arch_stage2a.py'):copy('build/'+name)
for label in ('castle','quake','fixtures'):
 folder=run/(label+'-packed');copy(folder/'input.json',label+'-packed-input.json')
 with zipfile.ZipFile(dest/(label+'-packed-capture.zip'),'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted((folder/'capture').glob('*')):
   if p.is_file():z.write(p,p.name)
configs={}
for p in sorted(run.glob('physical-*.json')):
 d=json.loads(p.read_text());ts=d.get('trials',[])
 if len(ts)!=3:continue
 row={'package':d['package'],'scope':d['scope'],'instrumented':d['instrumented'],'segments':d['segments'],'fps':[t['observed_fps'] for t in ts],'positions':[t['position'] for t in ts],'restored_status':d.get('restored_status')}
 if d['instrumented']:
  row.update({'frames':[t['metrics']['frame'] for t in ts],'render_cycles':[t['phases']['render']['cycles'] for t in ts],'command_cycles':[t['metrics']['command_cycles'] for t in ts],'fifo_wait_cycles':[t['metrics']['fifo_wait_span_cycles'] for t in ts],'bytes':[t['metrics']['bytes'] for t in ts],'commands':[t['metrics']['commands'] for t in ts],'fine':{k:{field:[t['fine'][k][field] for t in ts] for field in ('cycles','calls')} for k in ts[0].get('fine',{})}})
 else:
  row['live_timer_cycles']={k:[t['metrics'][k] for t in ts] for k in ts[0]['metrics']}
  row['median_update_plus_render_ms']=statistics.median(row['live_timer_cycles']['game_cpu_cycles'])/50000
 configs[p.stem]=row
base=configs.get('physical-legacy-detail')
if base:
 for k,row in configs.items():
  if 'render_cycles' not in row:continue
  row['median_render_ms']=statistics.median(row['render_cycles'])/50000
  row['median_command_ms']=statistics.median(row['command_cycles'])/50000
  if k.endswith('-detail'):
   row['render_change_percent_vs_legacy']=(statistics.median(row['render_cycles'])/statistics.median(base['render_cycles'])-1)*100
   row['command_change_percent_vs_legacy']=(statistics.median(row['command_cycles'])/statistics.median(base['command_cycles'])-1)*100
if 'physical-legacy-normal' in configs and 'physical-packed-normal' in configs:
 normal_base=configs['physical-legacy-normal']['median_update_plus_render_ms']
 configs['physical-packed-normal']['update_plus_render_change_percent_vs_legacy']=(configs['physical-packed-normal']['median_update_plus_render_ms']/normal_base-1)*100
fit=Path('build/quartus-arch-stage2a/ArchStage2ASoC.fit.summary').read_text();rpt=Path('build/quartus-arch-stage2a/ArchStage2ASoC.fit.rpt').read_text();sta=Path('build/quartus-arch-stage2a/ArchStage2ASoC.sta.summary').read_text()
slacks=[{'type':a.strip(),'slack_ns':float(b)} for a,b in re.findall(r'Type\s*:\s*([^\n]+)\nSlack\s*:\s*([-+\d.]+)',sta)]
resources={key:int(re.search(label+r'\s*:\s*([\d,]+)',fit).group(1).replace(',','')) for key,label in [('logic_elements','Total logic elements'),('logical_memory_bits','Total memory bits'),('multiplier_9bit_elements','Embedded Multiplier 9-bit elements'),('plls','Total PLLs')]}
resources['m9k_blocks']=int(re.search(r'; M9Ks\s*;\s*([\d,]+)' ,rpt).group(1).replace(',',''))
resources['worst_setup_ns']=min(t['slack_ns'] for t in slacks if ' Setup ' in t['type']);resources['worst_hold_ns']=min(t['slack_ns'] for t in slacks if ' Hold ' in t['type']);resources['reported_slacks']=slacks
measure={'date':'2026-10-11','source_baseline':'460957e','implementation_commit':'2f226d6','clock_hz':50000000,'scope':'Three standing-spawn trials per transport/profiling configuration plus three packed moving diagnostics on one Stage 2 image; completed-frame snapshots, not a route distribution. Normal live timers are non-atomic. No FPS or full-game equivalence claim.','configurations':configs,'fitted':resources}
(dest/'measurements.json').write_text(json.dumps(measure,indent=2)+'\n')
sources=['rtl/soc_mmio.sv','rtl/udp_memory_loader.sv','firmware/src/gfx.c','firmware/include/soc.h','scripts/load_game.py','scripts/profile_cpu.py','scripts/soc.py','scripts/replay_render_route.py','sim/packed_mmio_tb.sv','sim/packed_render_replay_tb.sv','sim/render_frame_replay_tb.sv','scripts/test_packed_gfx.py','scripts/test_gpu_fractional.py']
for p in sources:copy(p,'source-'+Path(p).name)
packages=[]
for d in configs.values():
 for seg in d['segments']:
  p=Path(d['package']).parent/seg['file']
  if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()!=seg['sha256']:raise ValueError('Changed binary '+str(p))
  if seg['address']==0:
   for suffix in ('.bin','.package.json','.symbols.json','.isa.json','.map'):copy(p.with_suffix(suffix))
artifacts=sources+['build/quartus-screen-edges/ScreenEdgesSoC.sof','build/quartus-arch-stage1/ArchStage1SoC.sof','build/quartus-arch-stage2a/ArchStage2ASoC.sof']+[str(p) for p in Path('rtl/generated').glob('*') if p.is_file()]+[str(p) for p in Path('build').glob('mario-castle-sdram-direct*mul.bin')]+['build/arch-stage1/baseline/mario-castle-sdram-direct-mul.bin','build/arch-stage1/baseline/mario-castle-sdram-direct-mul.assets.bin','build/arch-stage2a/attempt-1-status-preflight/ArchStage2ASoC.sof']
manifest={'date':'2026-10-11','baseline_commit':'460957e','implementation_commit':'2f226d6','clocks':'SoC 50 MHz; SDRAM and VGA clocks unchanged','tools':{'quartus':'18.1.0 Build 625 Lite','modelsim':'ModelSim-Altera 10.5b'},'artifacts':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in artifacts if Path(p).is_file()},'raw_evidence':{str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'configurations':{k:{'render_ms':v.get('median_render_ms'),'command_ms':v.get('median_command_ms'),'change_percent':v.get('render_change_percent_vs_legacy')} for k,v in configs.items()},'resources':{k:v for k,v in resources.items() if k!='reported_slacks'}},indent=2))
