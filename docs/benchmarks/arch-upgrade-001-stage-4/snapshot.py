from pathlib import Path
import json,hashlib,shutil,subprocess,sys
sys.path.insert(0,'scripts');import soc
out=Path('build/arch-stage4');snap=out/'source-snapshot';snap.mkdir(parents=True,exist_ok=True)
files=soc.sources(True)+[Path(x) for x in ('scripts/soc.py','scripts/gpu_setup.py','scripts/gpu_pixel_lanes.py','scripts/build_pixel_lanes.py','scripts/measure_pixel_lanes.py','scripts/measure_setup_overlap.py','scripts/profile_cpu.py','scripts/replay_render_route.py','scripts/compare_render_frames.py','sim/pixel_lanes_tb.sv','sim/pixel_banks_tb.sv','sim/render_frame_replay_tb.sv','sim/screen_edge_coverage_tb.sv','sim/depth_edge_coverage_tb.sv','firmware/tests/setup_overlap_probe.c','upstream.lock.json','fpga/soc.sdc','build/boot.json','build/firmware.mif','build/firmware.hex')]
files+=list(Path('rtl').glob('*.sdc'))+list(Path('rtl/generated').glob('*.svh'))
for p in files:
 p=p.resolve()
 if not p.is_file():continue
 rel=p.relative_to(Path.cwd());q=snap/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
prov={'date':'2026-10-11','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'baseline_commit':'8082afd','accepted_stage3_commit':'0a6434b','accepted_sof_sha256':'eb28b7007c48fc799ec729655d83a823112ea15c73a06cac665c32e9f1037f62','clock_hz':50000000,'tools':{'Quartus':'18.1.0 Build 625 Lite','ModelSim':'10.5b'},'source_hashes':{str(p.relative_to(snap)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in snap.rglob('*') if p.is_file()}}
(out/'provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
print('Snapshotted',len(prov['source_hashes']),'source/configuration files')
