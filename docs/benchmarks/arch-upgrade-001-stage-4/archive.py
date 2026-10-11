from pathlib import Path
import json,hashlib,shutil,subprocess
root=Path('build/arch-stage4');dest=Path('docs/benchmarks/arch-upgrade-001-stage-4');dest.mkdir(parents=True,exist_ok=True)
for p in root.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(root)
 if any(part.endswith('lib') or part=='simlib' for part in rel.parts):continue
 if p.suffix not in ('.json','.log','.py','.qsf','.hex','.meta','.sv','.svh','.v','.c','.h','.sdc','.mif','.map','.txt','.bin','.elf'):continue
 if p.suffix in ('.bin','.elf') and rel.parts[0]!='probe':continue
 q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for mode,name in [('control','ArchStage4ControlSoC'),('dual','ArchStage4SoC')]:
 fit=Path('build/quartus-arch-stage4-'+mode)
 for p in fit.iterdir():
  if p.suffix in ('.rpt','.summary'):
   q=dest/'quartus'/mode/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for stem in ('mario-castle-sdram-direct-packed-mul','mario-castle-sdram-direct-profile-detail-packed-mul'):
 for suffix in ('.bin','.package.json','.symbols.json','.isa.json','.map'):
  p=Path('build')/(stem+suffix)
  if p.is_file():
   q=dest/'firmware'/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
files={str(p.relative_to(dest)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in dest.rglob('*') if p.is_file() and p.name!='manifest.json'}
measure=json.loads((dest/'measurements.json').read_text())
manifest={'date':'2026-10-11','baseline_commit':'8082afd','accepted_stage3_commit':'0a6434b','implementation_commits':['b465b03','721fada'],'decision':json.loads((root/'decision.json').read_text()),'clock_hz':50000000,'tools':{'Quartus':'18.1.0 Build 625 Lite','ModelSim':'10.5b'},'physical_trials':18,'trial_order':'dual then control; three resets for probe, ordinary standing and instrumented standing per image','files':files,'hardware':measure['hardware'],'coverage':'17 exact shared-terrain/fixture replay frames against accepted Stage 3 captures and exact seven event counters; excludes full actors/transitions/physical framebuffer and complete-level traversal. Raw bytes preserved.'}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Archived',len(files),'files; bytes',sum(x['bytes'] for x in files.values()))
