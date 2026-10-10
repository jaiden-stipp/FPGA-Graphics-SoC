import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,package_segments,require_hardware
trial=Path('build/mario-castle-sdram-direct.package.json')
old=json.loads(Path('build/mario-castle-floor-rollback.package.json').read_text())
rollback=Path('build/mario-castle-floor-rollback.bin').read_bytes()
assert hashlib.sha256(rollback).hexdigest()==old['segments'][0]['sha256']
segments=package_segments(trial);spec=json.loads(trial.read_text())
assert spec['segments'][1]['sha256']==old['segments'][1]['sha256'],'Asset changes require a full load'
report={'method':'CPU-only verified UDP load; same asset hash as previous package', 'baseline_cpu_sha256':hashlib.sha256(rollback).hexdigest(),'candidate_cpu_sha256':spec['segments'][0]['sha256'],'cpu_bytes':spec['segments'][0]['bytes'],'assets_sha256':spec['segments'][1]['sha256']}
l=Loader();attempt=False
try:
 require_hardware(l,spec);report['before']=l.operation(STATUS);attempt=True
 l.transfer([s for s in segments if s[0]==0]);report['cpu_upload_readback_verified']=True
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  s=l.operation(STATUS)
  if s['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Boot failed')
  if 0<s['scratch']<0x10000000:break
  time.sleep(.05)
 else:raise TimeoutError('No completed frame')
 report['first_frame']=s
 time.sleep(2);report['later']=l.operation(STATUS)
 assert report['later']['scratch']!=s['scratch'],'Frame count did not advance'
 report['left_running']='mario-castle-sdram-direct with rising-floor sweep correction'
 print(json.dumps(report),flush=True)
except BaseException:
 if attempt:l.transfer([(0,rollback,'previous Mario CPU')]);report['restored']=l.operation(STATUS)
 raise
finally:
 l.close();Path('build/floor-fix-board.json').write_text(json.dumps(report,indent=2)+'\n')
