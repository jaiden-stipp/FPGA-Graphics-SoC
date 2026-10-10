from pathlib import Path
import json, hashlib, statistics, shutil, subprocess

root=Path(__file__).resolve().parents[2]
out=root/'docs/benchmarks/post-mul-review-001'
out.mkdir(parents=True,exist_ok=True)
report={'date':'2026-10-10','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'clock_hz_configured':50000000,'cases':{},'evidence':[]}
def med(items): return statistics.median(items)
for name in ('standing','moving'):
    path=root/'build/post-mul-review'/f'{name}.json'
    raw=json.loads(path.read_text()); ts=raw['trials']
    assert len(ts)==3 and 'failure' not in raw and not raw['restored_status']['held']
    c={'fps_median':med([t['observed_fps'] for t in ts]),'fps_range':[min(t['observed_fps'] for t in ts),max(t['observed_fps'] for t in ts)],'frames':[t['metrics']['frame'] for t in ts],'positions':[t['position'] for t in ts]}
    for category in ('metrics','gpu','phases','detail'):
        if category in ('phases','detail'):
            c[category]={key:{field:med([t[category][key][field] for t in ts]) for field in ts[0][category][key]} for key in ts[0][category]}
        else:c[category]={key:med([t[category][key] for t in ts]) for key in ts[0][category]}
    render=c['phases']['render']
    c['render_memory_freeze_percent']=100*render['memory_freezes']/render['cycles']
    c['render_dependency_bubble_percent']=100*render['dependency_bubbles']/render['cycles']
    c['render_ipc']=render['retired']/render['cycles']
    c['command_percent_of_render']=100*c['metrics']['command_cycles']/render['cycles']
    c['gpu_pre_swap_cycles']=med([t['gpu']['total_cycles']-t['gpu']['swap_wait_cycles'] for t in ts])
    report['cases'][name]=c
    shutil.copyfile(path,out/path.name)
files=['scripts/profile_cpu.py','scripts/load_game.py','firmware/src/world.c','firmware/src/gfx.c','firmware/src/game_runtime.c','firmware/src/portable_main.c','external/renderer/rtl/pipeline/render_performance_counters.sv','external/renderer/rtl/video/vga_page_swap_controller.sv','rtl/generated/graphics_pipeline.sv','build/post-mul-review/summarize.py']
for file in files:
    p=root/file; dest=out/('source-'+p.name);shutil.copyfile(p,dest)
for stem in ('mario-castle-sdram-direct-profile-detail-mul','mario-castle-sdram-direct-mul'):
    for suffix in ('.package.json','.symbols.json','.bin','.assets.bin'):
        p=root/'build'/(stem+suffix)
        report.setdefault('artifacts',[]).append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        if suffix.endswith('json'):shutil.copyfile(p,out/(stem+suffix))
sof=root/'build/quartus-integer-mul/IntegerMulSoC.sof'
report['sof_sha256']=hashlib.sha256(sof.read_bytes()).hexdigest()
for p in sorted(out.iterdir()):
    if p.name!='measurements.json':report['evidence'].append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report['cases'],indent=2))
