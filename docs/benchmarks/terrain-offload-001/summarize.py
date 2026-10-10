from pathlib import Path
import json,hashlib,statistics,shutil,subprocess
root=Path(__file__).resolve().parents[2];raw=root/'build/terrain-offload';out=root/'docs/benchmarks/terrain-offload-001';out.mkdir(parents=True,exist_ok=True)
names=['before','direct','safe','fine-direct','fine-safe','fine-safe-moving','fixture-direct','fixture-safe','fixture-fine-safe']
median=statistics.median
report={'date':'2026-10-10','baseline_revision':'6b8a298','candidate_revision':'3cec385','clock_hz_configured':50000000,'cases':{},'artifacts':[],'evidence':[]}
events=['triangles_submitted','triangles_clipped','triangles_culled','bounding_box_pixels','pixels_inside','depth_rejected','pixels_written']
for name in names:
    r=json.loads((raw/(name+'.json')).read_text());ts=r['trials'];assert len(ts)==3 and 'failure' not in r and not r['restored_status']['held']
    result={'median_fps':median(t['observed_fps'] for t in ts),'fps_range':[min(t['observed_fps'] for t in ts),max(t['observed_fps'] for t in ts)],'positions':[t['position'] for t in ts]}
    for section in ('phases','metrics','gpu','detail','fine','fine_events'):
        if section not in ts[0]:continue
        if section in ('phases','detail','fine'):
            result[section]={k:{f:median(t[section][k][f] for t in ts) for f in ts[0][section][k]} for k in ts[0][section]}
        else:result[section]={k:median(t[section][k] for t in ts) for k in ts[0][section]}
    if 'fine' in ts[0]:
        for t in ts:
            assert t['fine']['command_writes']['calls']==t['metrics']['bytes']
            assert t['fine']['command_crc']['calls']==t['metrics']['bytes']-2*t['metrics']['commands']
            assert t['fine']['clip_fraction']['calls']==t['fine']['clip_intersection']['calls']
    report['cases'][name]=result;shutil.copyfile(raw/(name+'.json'),out/(name+'.json'))
    package=Path(r['package']);stem=package.name.removesuffix('.package.json')
    for suffix in ('.package.json','.symbols.json','.isa.json','.bin','.assets.bin'):
        p=package.parent/(stem+suffix)
        report['artifacts'].append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        if suffix.endswith('.json'):shutil.copyfile(p,out/p.name)

def signatures(labels):
    return {tuple(t['gpu'][e] for e in events) for label in labels for t in json.loads((raw/(label+'.json')).read_text())['trials']}
assert len(signatures(names[:5]))==1
assert len(signatures(names[-3:]))==1
report['castle_matched_gpu_events']=dict(zip(events,next(iter(signatures(names[:5])))))
report['fixture_matched_gpu_events']=dict(zip(events,next(iter(signatures(names[-3:])))))
c=report['cases'];report['fixture_render_reduction_percent']=100*(1-c['fixture-safe']['phases']['render']['cycles']/c['fixture-direct']['phases']['render']['cycles'])
report['direct_control_render_change_percent']=100*(c['direct']['phases']['render']['cycles']/c['before']['phases']['render']['cycles']-1)
report['safe_vs_direct_render_change_percent']=100*(c['safe']['phases']['render']['cycles']/c['direct']['phases']['render']['cycles']-1)
report['fine_direct_added_render_cycles']=c['fine-direct']['phases']['render']['cycles']-c['direct']['phases']['render']['cycles']
for file in ('experiment.json','experiment.log','fixture.log','normal-safe-build.log','castle-admission.json','inspect_castle.py','castle-admission.c','fixture.py','summarize.py','restored-mario.json'):
    shutil.copyfile(raw/file,out/file)
for file in ('world.json','game.project.json','port.c'):
    shutil.copyfile(raw/'fixture'/file,out/('fixture-'+file))
stem='mario-castle-sdram-gpu-safe-mul'
report['unmeasured_normal_candidate']=[]
for suffix in ('.package.json','.symbols.json','.isa.json','.bin','.assets.bin'):
    p=root/'build'/(stem+suffix)
    report['unmeasured_normal_candidate'].append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    if suffix.endswith('.json'):shutil.copyfile(p,out/p.name)
files=['firmware/include/cpu_profile.h','firmware/include/world.h','firmware/src/cpu_profile.c','firmware/src/gfx.c','firmware/src/world.c','scripts/profile_cpu.py','scripts/measure_terrain_offload.py','scripts/test_terrain_offload.py','scripts/soc.py','scripts/rv32i_subset.py','scripts/run.ps1','scripts/world_assets.py']
for file in files:shutil.copyfile(root/file,out/('source-'+Path(file).name))
for file in ('firmware/src/gfx.c','firmware/src/world.c'):
    (out/('baseline-'+Path(file).name)).write_bytes(subprocess.check_output(['git','show','6b8a298:'+file],cwd=root))
sof=root/'build/quartus-integer-mul/IntegerMulSoC.sof';report['existing_sof_sha256']=hashlib.sha256(sof.read_bytes()).hexdigest()
for p in sorted(out.iterdir()):
    if p.name!='measurements.json':report['evidence'].append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('cases','artifacts','evidence')},indent=2))
for name in names:
    case=c[name];print(name,'render',case['phases']['render']['cycles'],'command',case['metrics']['command_cycles'],'fps',case['median_fps'],'events',case.get('fine_events',{}))
print('FINE DIRECT',json.dumps(c['fine-direct']['fine']))
print('FINE MOVING',json.dumps(c['fine-safe-moving']['fine']))
