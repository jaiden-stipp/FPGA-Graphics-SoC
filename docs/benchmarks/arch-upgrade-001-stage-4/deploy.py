from pathlib import Path
import json,hashlib,subprocess,sys,time,re
sys.path.insert(0,'scripts')
from measure_pixel_lanes import restore_accepted,timing_gate
from load_game import Loader,STATUS,package_segments,require_hardware
out=Path('build/arch-stage4');measure=json.loads((out/'measurements.json').read_text())
for kind in ('castle','quake','fixtures'):
 if not measure['replays'][kind]['exact']:raise RuntimeError('Replay gate failed')
for mode in ('control','dual'):
 if any(v for k,value in measure['hardware'][mode].items() if k.startswith('unconstrained') for v in value.values()):raise RuntimeError('Constraint gate failed')
for i in range(3):
 if measure['physical']['dual']['probe'][i]['before_swap_wait']['median']>=measure['physical']['control']['probe'][i]['before_swap_wait']['median']:raise RuntimeError('Probe benefit gate failed')
# Compare ordinary samples to values actually observed on accepted Stage 3.
accepted=json.loads(Path('docs/benchmarks/arch-upgrade-001-stage-3/measurements.json').read_text())
prior=accepted['physical']['overlap']['normal']['game_cpu_cycles']
new=measure['physical']['dual']['normal']['game_cpu_cycles']
if new['minimum']<prior['minimum'] or new['maximum']>prior['maximum']:
 raise RuntimeError('Ordinary CPU samples outside accepted baseline range need review')
fit=Path('build/quartus-arch-stage4-dual');name='ArchStage4SoC';timing_gate(fit,name)
sof=fit/(name+'.sof');expected=measure['hardware']['dual']['sof_sha256']
if hashlib.sha256(sof.read_bytes()).hexdigest()!=expected:raise RuntimeError('SOF changed')
package=Path('build/mario-castle-sdram-direct-packed-mul.package.json');spec=json.loads(package.read_text())
if spec['segments'][0]['sha256']!='4cfe0c4811c35df0f14b1269f5d6eed628d8c97a19483ac1cd224d9b06cf8eda':raise RuntimeError('Normal firmware changed')
if spec['segments'][1]['sha256']!='afa690e2965016a9ce5cec307a34942856f6b573a551a5761e9f5738dd1f4cc6':raise RuntimeError('Assets changed')
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
  else:raise RuntimeError('Selected Stage 4 Mario did not resume')
  time.sleep(1);last=loader.operation(STATUS)
  if last['held'] or last['scratch']<=first['scratch'] or last['gpu_features']!=3:raise RuntimeError('Stage 4 progress failed')
  result={'decision':'Stage 4 accepted as optional reusable two-lane/banked-memory upgrade; normal packed Mario selected; single-lane fallback retained. Synthetic GPU gain and shorter representative GPU activity; ordinary standing CPU/FPS unchanged within animation sampling spread.','sof':str(sof),'sof_sha256':expected,'package':str(package),'segments':spec['segments'],'first_status':first,'last_status':last}
  (out/'accepted-running-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 finally:loader.close()
except Exception:
 restore_accepted();raise
