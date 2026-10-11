from pathlib import Path
import json,hashlib,shutil,subprocess
root=Path('build/arch-stage3');dest=Path('docs/benchmarks/arch-upgrade-001-stage-3');dest.mkdir(parents=True,exist_ok=True)
# Refresh changed measurement-source snapshots; fitted RTL remains unchanged.
for name in ('scripts/measure_setup_overlap.py','scripts/gpu_setup.py','scripts/soc.py'):
 p=root/'source-snapshot'/name;p.write_bytes(Path(name).read_bytes())
for name in ('upstream.lock.json','build/firmware.mif','build/firmware.hex','build/boot.json'):
 p=Path(name)
 if p.is_file():
  q=root/'source-snapshot'/p;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
prov=json.loads((root/'provenance.json').read_text())
prov['source_hashes']={str(p.relative_to(root/'source-snapshot')).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'source-snapshot').rglob('*') if p.is_file()}
prov['head']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
(root/'provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
# Copy finite evidence only: no simulator database, full game assets or SOFs.
for p in root.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(root)
 if any(part.endswith('lib') or part=='simlib' for part in rel.parts):continue
 if p.suffix not in ('.json','.log','.py','.qsf','.hex','.meta','.sv','.svh','.v','.c','.h','.sdc','.mif','.map','.txt','.bin','.elf'):continue
 if p.suffix in ('.bin','.elf') and rel.parts[0]!='probe':continue
 q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for mode,name in [('serial','ArchStage3SerialSoC'),('overlap','ArchStage3SoC')]:
 fit=Path('build/quartus-arch-stage3-'+mode)
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
manifest={'date':'2026-10-11','baseline_commit':'6153efa','implementation_commits':['2bf56dd','8ee9eed','8bb928c','0d10359'],'decision':'Optional setup/raster overlap accepted and loaded with unchanged packed Mario; global serial fallback retained; no ordinary CPU/FPS gain','clock_hz':50000000,'tools':{'Quartus':'18.1.0 Build 625 Lite','ModelSim':'10.5b'},'physical_trials':18,'files':files,'hardware':measure['hardware'],'coverage':'17 exact shared-terrain/fixture frames in both rebuilt modes; excludes full actors/transitions/physical framebuffer and complete-level traversal. Synthetic probes are not game speedups. Raw bytes preserved.'}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Archived',len(files),'files; bytes',sum(x['bytes'] for x in files.values()))
