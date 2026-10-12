from pathlib import Path
import json,hashlib,shutil
root=Path('build/arch-stage5');dest=Path('docs/benchmarks/arch-upgrade-001-stage-5');dest.mkdir(parents=True,exist_ok=True)
for p in root.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(root)
 if any(part.endswith('lib') or part=='simlib' for part in rel.parts):continue
 if p.suffix not in ('.json','.log','.py','.qsf','.hex','.meta','.sv','.svh','.v','.c','.h','.sdc','.mif','.map','.txt','.bin','.elf'):continue
 if p.suffix in ('.bin','.elf') and not p.name.startswith('probe.'):continue
 q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for mode,name in [('control','ArchStage5ControlSoC'),('worker','ArchStage5SoC')]:
 for p in Path('build/quartus-arch-stage5-'+mode).iterdir():
  if p.suffix in ('.rpt','.summary'):
   q=dest/'quartus'/mode/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for stem in ('mario-castle-sdram-direct-packed-mul','mario-castle-sdram-direct-profile-detail-packed-mul','mario-castle-sdram-direct-packed-mul-geometry','mario-castle-sdram-direct-profile-detail-packed-mul-geometry'):
 for suffix in ('.bin','.package.json','.symbols.json','.isa.json','.map'):
  p=Path('build')/(stem+suffix)
  if p.is_file():
   q=dest/'firmware'/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
files={str(p.relative_to(dest)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json'}
r=json.loads((dest/'measurements.json').read_text())
manifest={'date':'2026-10-11','baseline_commit':'40219cec','accepted_stage4_commit':'e0d776c','implementation_commits':['b677581','df0649df','765ecbe'],'decision':'Optional geometry worker accepted and selected with normal worker-enabled packed Mario. Ordinary standing CPU improvement; FPS around 30; Stage 4 rollback preserved.','clock_hz':50000000,'tools':{'Quartus':'18.1.0 Build 625 Lite','ModelSim':'10.5b'},'complete_raw_physical_trials':15,'additional_exploratory_trials_logged':3,'trial_order':'worker paired probe/normal/detail, then control normal/detail; exploratory probe preceded these','files':files,'hardware':r['hardware'],'coverage':'1152 independent/production CPU oracle vertices; three complete standing actor/game CPU/cache/SDRAM command streams and composed GPU color/depth/palette/triangle replays. Synthetic decoder backpressure/immediate presentation ack; no equivalence timing claim. Not full-level traversal or physical framebuffer acceptance. Raw bytes preserved.'}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Archived',len(files),'files;',sum(v['bytes'] for v in files.values()),'bytes')
