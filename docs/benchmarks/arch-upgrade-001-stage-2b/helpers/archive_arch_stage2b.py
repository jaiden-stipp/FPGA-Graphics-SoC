from pathlib import Path
import hashlib,json,shutil,re,subprocess
root=Path('.').resolve();out=root/'docs/benchmarks/arch-upgrade-001-stage-2b';out.mkdir(parents=True,exist_ok=True)
def copy(src,dest):
 src=root/src;dest=out/dest
 if not src.is_file():raise RuntimeError('Missing '+str(src))
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
for p in (root/'build/arch-stage2b').iterdir():
 if p.is_file() and p.suffix in ('.json','.log','.qsf','.txt'):copy(p.relative_to(root),p.name)
for folder in ('attempt-1-timing','attempt-2-global-staging','castle-dma','quake-dma','fixtures-dma'):
 for p in (root/'build/arch-stage2b'/folder).rglob('*'):
  if p.is_file() and p.suffix!='.elf':copy(p.relative_to(root),Path(folder)/p.relative_to(root/'build/arch-stage2b'/folder))
for p in (root/'build/quartus-arch-stage2b').glob('ArchStage2BSoC.*'):
 if p.suffix in ('.rpt','.summary'):copy(p.relative_to(root),Path('final-fit')/p.name)
for name in ('dma-regression.log','dma-fw.log','dma-detail-fw.log','dma-native.log','dma-quartus.log','dma-final-replays.log'):
 copy(Path('build')/name,Path('logs')/name)
for name in ('build_arch_stage2b.py','measure_arch_stage2b.py','measure_arch_stage2b_local.py','restore_arch_stage2b.py','replay_arch_stage2b.py','summarize_arch_stage2b.py','archive_arch_stage2b.py'):
 copy(Path('build')/name,Path('helpers')/name)
for stem in ('mario-castle-sdram-direct-packed-mul','mario-castle-sdram-direct-profile-detail-packed-mul','mario-castle-sdram-direct-dma-mul','mario-castle-sdram-direct-profile-detail-dma-mul'):
 for suffix in ('.bin','.package.json','.symbols.json','.isa.json','.map'):copy(Path('build')/(stem+suffix),Path('firmware')/(stem+suffix))
for name in ('harness.c',):copy(Path('build/dma-native')/name,Path('native')/name)
source_paths=set()
for line in (root/'build/arch-stage2b/project.qsf').read_text().splitlines():
 if any('-name '+kind+' ' in line for kind in ('SYSTEMVERILOG_FILE','VERILOG_FILE','SDC_FILE')):
  source_paths.add(Path(line.split()[-1].strip('"')))
source_paths.update(Path(p) for p in ('rtl/soc_memory.sv','rtl/soc_mmio.sv','rtl/boards/de2_115_soc_top.sv','rtl/udp_controls.sv','rtl/udp_memory_loader.sv','rtl/gfx_command_dma.sv','rtl/sdram_command_arbiter.sv','firmware/src/gfx.c','firmware/src/cpu_profile.c','firmware/include/soc.h','firmware/src/portable_main.c','firmware/src/game_runtime.c','scripts/soc.py','scripts/load_game.py','scripts/profile_cpu.py','scripts/replay_render_route.py','scripts/test_dma_gfx.py','scripts/test_gfx_staging.py','scripts/measure_gfx_staging.py','sim/gfx_dma_tb.sv','sim/sdram_arbiter_tb.sv','sim/gfx_dma_memory_tb.sv','sim/render_frame_replay_tb.sv','sim/dma_render_replay_tb.sv','sim/sdram_device_model.sv'))
project=json.loads((root/'build/castle/game.project.json').read_text())
source_paths.update((Path('build/castle')/p).resolve().relative_to(root) for p in project['port']['sources'])
for p in sorted(source_paths):copy(p,Path('sources')/p)
copy(Path('build/castle/game.project.json'),Path('provenance/game.project.json'))
artifacts={}
for p in source_paths:artifacts[p.as_posix()]=hashlib.sha256((root/p).read_bytes()).hexdigest()
local_only=[Path('build/quartus-arch-stage2a/ArchStage2ASoC.sof'),Path('build/quartus-arch-stage2b/ArchStage2BSoC.sof')]
for stem in ('mario-castle-sdram-direct-packed-mul','mario-castle-sdram-direct-profile-detail-packed-mul','mario-castle-sdram-direct-dma-mul','mario-castle-sdram-direct-profile-detail-dma-mul'):
 local_only += [Path('build')/(stem+s) for s in ('.elf','.assets.bin')]
local_only += list((root/'build/arch-stage2b/attempt-2-global-staging').glob('*.elf'))
for p in local_only:
 rel=p.relative_to(root) if p.is_absolute() else p;artifacts[rel.as_posix()]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
provenance={}
for p in (root/'firmware/generated').glob('*'):
 if p.is_file():provenance[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in (root/'build/castle').glob('*.json'):provenance[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'date':'2026-10-11','baseline_commit':'df9c539','hardware_implementation_commit':'59a4d3a','local_staging_commit':'40e4ee1','tools':{'quartus':'18.1.0 Build 625 Lite','modelsim':'10.5b','llvm':'Configured local LLVM, exact ISA/subset logs retained'},'clocks':'50 MHz SoC; SDRAM and VGA clocks unchanged','decision':'DMA not promoted; accepted Stage 2A image and packed Mario restored','source_hash_scope':'Exact compiler-read workspace bytes archived in sources; normal Git source newline normalization can differ. Raw evidence -text preserves these bytes.','artifacts':artifacts,'generated_provenance_hashes':provenance,'local_only_artifacts':[str(p.relative_to(root) if p.is_absolute() else p).replace('\\','/') for p in local_only],'raw_files':{p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.rglob('*') if p.is_file() and p.name!='manifest.json'}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Check report constants against actual fit and timing source reports.
fit=(root/'build/quartus-arch-stage2b/ArchStage2BSoC.fit.summary').read_text()
assert re.search(r'Total logic elements\s*:\s*23,788',fit)
assert re.search(r'Total memory bits\s*:\s*2,659,688',fit)
assert all(json.loads((out/(n+'-comparison.json')).read_text())['exact'] for n in ('castle','quake','fixtures'))
assert json.loads((out/'final-running-check.json').read_text())['last_status']['scratch']==32
print('Archived',len(manifest['raw_files']),'raw files; exact replays and rollback checks verified')
