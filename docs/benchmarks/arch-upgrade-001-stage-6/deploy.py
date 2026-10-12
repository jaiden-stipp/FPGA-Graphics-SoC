import json,hashlib,time,sys
from pathlib import Path
sys.path.insert(0,'scripts')
from measure_render_cadence import OUT,FIT,SOF,SOF_SHA,STEM,ready,restore,snapshot_baseline
from measure_pixel_lanes import timing_gate
from load_game import Loader,STATUS,package_segments,require_hardware
m=json.loads((OUT/'measurements.json').read_text())
if m['uncapped']['median_fps']<=1.5*m['tick-paced']['median_fps']:raise RuntimeError('No measured standing presentation benefit')
for mode in ('tick-paced','uncapped','moving-tick-paced','moving-uncapped'):
    report=json.loads((OUT/('physical-'+mode+'.json')).read_text())
    if len(report['trials'])!=3 or report.get('failure'):raise RuntimeError('Incomplete trials '+mode)
    if any(not t['cadence'].get('atomic') for t in report['trials']):raise RuntimeError('Non-atomic phases')
    if report['segments'][1]['sha256']!='afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6':raise RuntimeError('Assets changed')
for log,count in [('clock-tests.log',5),('world-tests.log',30)]:
    text=(OUT/log).read_text()
    if 'Ran '+str(count)+' tests' not in text or '\nOK' not in text:raise RuntimeError('Test gate failed '+log)
timing_gate(FIT,'ArchStage5SoC')
if hashlib.sha256(SOF.read_bytes()).hexdigest()!=SOF_SHA:raise RuntimeError('SOF changed')
package=Path('build')/(STEM+'-uncapped.package.json')
spec=json.loads(package.read_text())
if spec['segments']!=m['uncapped']['segments'] or spec['cadence']['simulation_tick_cycles']!=1666667:raise RuntimeError('Candidate changed')
loader=Loader()
try:
    require_hardware(loader,spec);loader.transfer(package_segments(package))
    first=ready(loader);time.sleep(1);last=loader.operation(STATUS)
    if last['held'] or last['scratch']<=first['scratch'] or last['cpu_features']!=0x80000003 or last['gpu_features']!=3:raise RuntimeError('Selected game failed to progress')
    (OUT/'accepted-running-check.json').write_text(json.dumps({'sof':str(SOF),'sof_sha256':SOF_SHA,'package':str(package.resolve()),'segments':spec['segments'],'cadence':spec['cadence'],'first_status':first,'last_status':last},indent=2)+'\n')
except BaseException:
    loader.close();restore(snapshot_baseline());raise
finally:loader.close()
print('Accepted uncapped Mario loaded; complete CPU/assets readback and frame progression verified.')
