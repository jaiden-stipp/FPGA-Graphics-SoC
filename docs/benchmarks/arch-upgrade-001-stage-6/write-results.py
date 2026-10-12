import json,hashlib,statistics,subprocess,shutil
from pathlib import Path
root=Path('.');out=root/'build/arch-stage6'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(label):
    d=json.loads((out/('physical-'+label+'.json')).read_text());trials=d['trials']
    if len(trials)!=3 or any(not t['cadence'].get('atomic') for t in trials):raise RuntimeError('Need three atomic trials '+label)
    fps=[t['observed_fps'] for t in trials]
    metrics={k:[t['metrics'][k] for t in trials] for k in trials[0]['metrics']}
    metrics['render_submission_cycles']=[t['metrics']['game_cpu_cycles']-t['metrics']['game_update_cycles'] for t in trials]
    metrics['tick_wait_cycles']=[t['cadence']['game_tick_wait_cycles'] for t in trials]
    return {'scope':d['scope'],'observed_fps':fps,'median_fps':statistics.median(fps),
        'metrics':metrics,'metric_medians':{k:statistics.median(v) for k,v in metrics.items()},
        'simulation_hz':[t['cadence']['simulation_hz'] for t in trials],
        'completed_frame_ids':[t['cadence']['frame'] for t in trials],
        'updates_in_sampled_frame':[t['cadence']['game_updates_this_frame'] for t in trials],
        'positions':[t['position'] for t in trials], 'segments':d['segments']}
a=summarize('tick-paced');b=summarize('uncapped')
m={'baseline_commit':'e50d34f49689646bead2ac1431302bf7e7c7afc5','accepted_stage5_commit':'c4f93877eb1c50b422046af8c1c89b9b1111a178',
   'firmware_implementation_commit':'a854e1ed41bbe2be926481489f6fccdc38106e97','hardware_changed':False,
   'clock_hz':50000000,'simulation_tick_cycles':1666667,'tick-paced':a,'uncapped':b,
   'median_presentation_fps_change_percent':100*(b['median_fps']/a['median_fps']-1),
   'timing':json.loads((out/'timing/audit.json').read_text()),
   'limits':['Standing spawn comparison; three completed-frame phase snapshots are not a frame-time distribution.',
             'More presentations can repeat the same 30 Hz simulation state; no interpolation, new-state rate or engine speedup claim.',
             'CPU submission, accelerator and GPU spans overlap; do not sum them as serial frame time.',
             'Preliminary non-atomic phase captures are excluded; frame-progress FPS remains exploratory evidence.',
             'Simulation Hz is ticks divided by elapsed cycles in fresh short reset trials, below 32-bit elapsed-counter wrap.']}
for mode in ('moving-tick-paced','moving-uncapped'):
    if (out/('physical-'+mode+'.json')).exists():m[mode]=summarize(mode)
(out/'measurements.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(m,indent=2))
