from pathlib import Path
import hashlib,json,subprocess,time,sys,shutil
sys.path.insert(0,'scripts')
from measure_setup_overlap import restore_accepted
from load_game import Loader,STATUS,package_segments,require_hardware
out=Path('build/arch-stage3');measure=json.loads((out/'measurements.json').read_text())
for mode in ('serial','overlap'):
 for kind in ('castle','quake','fixtures'):
  if not measure['replays'][mode][kind]['exact']:raise RuntimeError('Replay gate failed')
 if any(v for k,v in measure['hardware'][mode].items() if k.startswith('unconstrained') for v in v.values()):raise RuntimeError('Constraint coverage gate failed')
sof=Path('build/quartus-arch-stage3-overlap/ArchStage3SoC.sof')
expected=measure['hardware']['overlap']['sof_sha256']
if hashlib.sha256(sof.read_bytes()).hexdigest()!=expected:raise RuntimeError('SOF changed')
summary=Path('build/quartus-arch-stage3-overlap/ArchStage3SoC.sta.summary').read_text()
import re
if min(float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary))<0:raise RuntimeError('Timing gate failed')
package=Path('build/mario-castle-sdram-direct-packed-mul.package.json')
spec=json.loads(package.read_text())
if spec['segments'][0]['sha256']!='4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda':raise RuntimeError('Normal firmware changed')
if spec['segments'][1]['sha256']!='afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6':raise RuntimeError('Assets changed')
shutil.copyfile(out/'final-running-check.json',out/'overlap-restored-running-check.json')
try:
 with (out/'accepted-programming.log').open('w') as log:
  subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
 loader=Loader()
 try:
  require_hardware(loader,spec);loader.transfer(package_segments(package))
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   first=loader.operation(STATUS)
   if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
   time.sleep(.05)
  else:raise RuntimeError('Accepted Stage 3 Mario did not resume')
  time.sleep(1);last=loader.operation(STATUS)
  if last['held'] or last['scratch']<=first['scratch'] or last['gpu_features']!=3:raise RuntimeError('Stage 3 progress failed')
  result={'decision':'Stage 3 selected on board as optional reusable scheduling upgrade; global serial fallback retained. Synthetic GPU benefit, no ordinary standing CPU/FPS gain.','sof':str(sof),'sof_sha256':expected,'package':str(package),'segments':spec['segments'],'first_status':first,'last_status':last}
  (out/'accepted-running-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 finally:loader.close()
except Exception:
 restore_accepted();raise
