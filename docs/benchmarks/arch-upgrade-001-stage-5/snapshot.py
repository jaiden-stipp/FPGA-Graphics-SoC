from pathlib import Path
import subprocess,json,hashlib,shutil,sys
sys.path.insert(0,'scripts');import soc
out=Path('build/arch-stage5');snap=out/'source-snapshot';snap.mkdir(parents=True,exist_ok=True)
files=soc.sources(True)+list(Path('rtl/generated').glob('*.svh'))+[Path(p) for p in ('fpga/soc.sdc','upstream.lock.json','scripts/soc.py','scripts/gpu_pixel_lanes.py','scripts/gpu_setup.py','scripts/build_geometry_worker.py','scripts/measure_geometry_worker.py','scripts/build_geometry_probe.py','scripts/geometry_vectors.py','scripts/compare_geometry_game.py','scripts/load_game.py','scripts/profile_cpu.py','sim/geometry_worker_tb.sv','sim/cpu_geometry_tb.sv','sim/geometry_stream_tb.sv','sim/geometry_game_tb.sv','firmware/src/world.c','firmware/include/geometry_worker.h','firmware/tests/geometry_probe.c','firmware/generated/geometry_probe_data.h','build/firmware.mif','build/firmware.hex','build/boot.json')]
for p in files:
 p=p.resolve()
 if not p.is_file():continue
 rel=p.relative_to(Path.cwd());q=snap/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
(out/'provenance.json').write_text(json.dumps({'date':'2026-10-11','baseline_commit':'40219cec','accepted_stage4_commit':'e0d776c','hardware_implementation_commit':'df0649df','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'clock_hz':50000000,'source_hashes':{str(p.relative_to(snap)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in snap.rglob('*') if p.is_file()}},indent=2)+'\n')
print('Source/config snapshots',len(json.loads((out/'provenance.json').read_text())['source_hashes']))
