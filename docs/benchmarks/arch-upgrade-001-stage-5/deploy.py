from pathlib import Path
import sys,json,hashlib,subprocess,time
sys.path.insert(0,'scripts')
from measure_geometry_worker import restore_accepted,timing_gate,WORKER
from load_game import Loader,STATUS,package_segments,require_hardware
out=Path('build/arch-stage5');r=json.loads((out/'measurements.json').read_text())
for name in ('game-comparison.json','gpu-comparison.json'):
 if not json.loads((out/name).read_text())['exact']:raise RuntimeError('Equivalence gate failed')
for mode in ('control','worker'):
 if any(v for k,row in r['hardware'][mode].items() if k.startswith('unconstrained') for v in row.values()):raise RuntimeError('Constraint coverage gate')
if r['physical']['worker']['normal']['game_cpu_cycles']['maximum']>=r['physical']['control']['normal']['game_cpu_cycles']['minimum']:raise RuntimeError('Ordinary benefit gate failed')
fit=Path('build/quartus-arch-stage5-worker');timing_gate(fit,'ArchStage5SoC');sof=fit/'ArchStage5SoC.sof';expected=r['hardware']['worker']['sof_sha256']
if hashlib.sha256(sof.read_bytes()).hexdigest()!=expected:raise RuntimeError('SOF changed')
spec=json.loads(WORKER.read_text())
if spec['segments'][1]['sha256']!='afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6':raise RuntimeError('Assets changed')
try:
 with (out/'accepted-programming.log').open('w') as log:
  subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
 loader=Loader()
 try:
  require_hardware(loader,spec);loader.transfer(package_segments(WORKER));deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   first=loader.operation(STATUS)
   if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
   time.sleep(.05)
  else:raise RuntimeError('Mario did not resume')
  time.sleep(1);last=loader.operation(STATUS)
  if last['held'] or last['scratch']<=first['scratch'] or not last['cpu_features']&2 or last['gpu_features']!=3:raise RuntimeError('Stage 5 progress gate')
  (out/'accepted-running-check.json').write_text(json.dumps({'decision':'Optional Stage 5 geometry worker accepted; normal worker-enabled packed Mario selected; Stage 4 rollback preserved. Measured standing CPU update/render improvement, no uncapped FPS/power/Fmax claim.','sof':str(sof),'sof_sha256':expected,'package':str(WORKER),'segments':spec['segments'],'first_status':first,'last_status':last},indent=2)+'\n')
  print('Selected Stage 5; frame progression',first['scratch'],last['scratch'])
 finally:loader.close()
except Exception:
 restore_accepted();raise
