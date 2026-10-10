import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,package_segments,require_hardware
baseline=Path('build/mario-castle-sdram.package.json');trial=Path('build/mario-castle-sdram-direct.package.json')
a=package_segments(baseline);b=package_segments(trial)
assert [(p,d) for p,d,_ in a if p>=0x80000000]==[(p,d) for p,d,_ in b if p>=0x80000000], 'Assets differ; CPU-only trial unsafe'
restore=[s for s in a if s[0]==0];cpu=[s for s in b if s[0]==0]
for stem in ('mario-castle-sdram-direct','mario-castle-sdram-direct-test'):
 path=Path('build')/(stem+'.package.json');spec=json.loads(path.read_text());spec['diagnostic']={'terrain_submission':'CPU-clipped direct triangles; GPU resident terrain cache bypassed','purpose':'isolate terrain mesh uploads and cached-versus-direct clipping; not a performance optimization'};path.write_text(json.dumps(spec,indent=2)+'\n')
report={'method':'CPU-only diagnostic load; backing assets unchanged','baseline_cpu_sha256':hashlib.sha256(restore[0][1]).hexdigest(),'trial_cpu_sha256':hashlib.sha256(cpu[0][1]).hexdigest(),'assets_sha256':hashlib.sha256([d for p,d,_ in b if p>=0x80000000][0]).hexdigest()}
l=Loader();attempt=False
try:
 require_hardware(l,json.loads(trial.read_text()));report['before']=l.operation(STATUS);attempt=True;l.transfer(cpu)
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  s=l.operation(STATUS)
  if s['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Diagnostic boot failed')
  if s['scratch']>0 and s['scratch']<0x10000000:break
  time.sleep(.05)
 else:raise TimeoutError('No diagnostic frame completion')
 report['running']=s;report['left_running']='mario-castle-sdram-direct'
 print(json.dumps(report),flush=True)
except BaseException:
 if attempt:l.transfer(restore);report['restored']=l.operation(STATUS)
 raise
finally:
 l.close();Path('build/terrain-direct-board.json').write_text(json.dumps(report,indent=2)+'\n')
