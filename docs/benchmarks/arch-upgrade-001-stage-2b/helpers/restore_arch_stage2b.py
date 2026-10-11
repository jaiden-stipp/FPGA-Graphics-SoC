from pathlib import Path
import sys,subprocess,json,hashlib,time
sys.path.insert(0,str(Path('scripts').resolve()))
from load_game import Loader,STATUS,package_segments,require_hardware
sof=Path('build/quartus-arch-stage2a/ArchStage2ASoC.sof');out=Path('build/arch-stage2b')
expected='917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32'
if hashlib.sha256(sof.read_bytes()).hexdigest()!=expected:raise RuntimeError('Rollback SOF changed')
with (out/'rollback-programming.log').open('w') as log:
 subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
package=Path('build/mario-castle-sdram-direct-packed-mul.package.json');loader=Loader()
try:
 require_hardware(loader,json.loads(package.read_text()));loader.transfer(package_segments(package))
 deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  first=loader.operation(STATUS)
  if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
  time.sleep(.05)
 else:raise RuntimeError('Packed Mario did not resume '+str(first))
 time.sleep(1);last=loader.operation(STATUS)
 if last['held'] or last['scratch']<=first['scratch'] or last['gpu_features']!=3:raise RuntimeError('Rollback game progress failed')
 report={'decision':'DMA not promoted; restore accepted Stage 2A packed Mario','sof':str(sof),'sof_sha256':expected,'package':str(package),'segments':json.loads(package.read_text())['segments'],'first_status':first,'last_status':last}
 (out/'final-running-check.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:loader.close()
