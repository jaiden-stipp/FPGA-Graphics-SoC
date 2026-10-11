from pathlib import Path
import json,re,shutil,hashlib,subprocess
root=Path('build/arch-stage3')
files=['scripts/gpu_setup.py','scripts/soc.py','scripts/build_setup_overlap.py','scripts/measure_setup_overlap.py','scripts/replay_render_route.py','rtl/soc_memory.sv','rtl/boards/de2_115_soc_top.sv','sim/setup_overlap_tb.sv','sim/render_frame_replay_tb.sv','firmware/tests/setup_overlap_probe.c','fpga/soc.sdc']
files += [str(p).replace('\\','/') for p in Path('rtl/generated').iterdir() if p.is_file()]
files += [str(p).replace('\\','/') for p in Path('external/renderer/rtl').rglob('*') if p.is_file() and p.suffix in ('.sv','.svh','.v','.mif')]
files += [str(p).replace('\\','/') for p in Path('rtl').glob('*.sv')]
for name in sorted(set(files)):
 p=Path(name);out=root/'source-snapshot'/p;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out)
metadata={'baseline_commit':'6153efa','implementation_commits':['2bf56dd','8ee9eed'],'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tools':{'Quartus':'18.1.0 Build 625 Lite','ModelSim':'10.5b'},'clocks':'50 MHz CPU/renderer, unchanged SDRAM/VGA constraints','normal_package':json.loads(Path('build/mario-castle-sdram-direct-packed-mul.package.json').read_text()),'detailed_package':json.loads(Path('build/mario-castle-sdram-direct-profile-detail-packed-mul.package.json').read_text()),'source_hashes':{n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in sorted(set(files))}}
(root/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
print('Snapshot',len(set(files)),'source files')
