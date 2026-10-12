from pathlib import Path
import json,hashlib,shutil,subprocess
root=Path('.');out=root/'build/arch-stage6';dest=root/'docs/benchmarks/arch-upgrade-001-stage-6';dest.mkdir(parents=True,exist_ok=True)
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for p in out.rglob('*'):
 if p.is_file() and p.suffix in ('.json','.log','.py','.sdc','.qsf','.rpt','.summary','.txt','.bin','.c') and not p.name.endswith('.assets.bin'):
  copy(p,dest/p.relative_to(out))
stem='mario-castle-sdram-direct-packed-mul-geometry'
for tag in ('','-test','-uncapped','-uncapped-test'):
 for suffix in ('.bin','.isa.json','.symbols.json','.package.json'):
  p=root/'build'/(stem+tag+suffix);copy(p,dest/'firmware'/p.name)
old=root/'docs/benchmarks/arch-upgrade-001-stage-5/source-snapshot'
paths={p.relative_to(old) for p in old.rglob('*') if p.is_file()}
paths.update(Path(p) for p in subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r','a854e1ed41bbe2be926481489f6fccdc38106e97']).decode().splitlines())
paths.update(Path(p) for p in ('scripts/measure_render_cadence.py','scripts/portable_game.py','fpga/soc.sdc','build/castle/game.project.json','docs/architecture-stage-6.md'))
for rel in sorted(paths):
 p=root/rel
 if p.is_file():copy(p,dest/'source-snapshot'/rel)
provenance={'baseline_commit':'e50d34f49689646bead2ac1431302bf7e7c7afc5','firmware_implementation_commit':'a854e1ed41bbe2be926481489f6fccdc38106e97','accepted_hardware_commit':'df0649df','tool_versions':{'quartus':'18.1.0 Build 625 SJ Lite Edition','clang':'21.1.6'},'clocks':{'core_hz':50000000,'mii_rx_tx_hz':25000000,'sdram_inverted_core':True,'sdram_capture_phase_ps':4500,'pixel':'Existing derived PLL; see exact SDC/QSF/STA'},'tests':{'clock_capability_native':5,'castle_world_native':30,'final_physical_trials':12,'preliminary_physical_trials':6},'hardware_sources_exact':json.loads((out/'hardware-source-comparison.json').read_text())['exact'],'scope':'Firmware cadence only; unchanged Stage 5 fit/SOF. Final atomic timing snapshots and host-timed frame progress; movement input is wall-clock, not cycle-identical. Assets and SOF are hash-identified local artifacts, not duplicated here.'}
(dest/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
manifest={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(dest/'manifest.json').write_text(json.dumps({'algorithm':'sha256','files':manifest},indent=2)+'\n')
print('Archived',len(manifest),'files;',sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()),'bytes')
