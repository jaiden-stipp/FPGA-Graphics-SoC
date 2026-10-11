from pathlib import Path
import json,subprocess,sys,hashlib
sys.path.insert(0,str(Path('scripts').resolve()))
from profile_cpu import collect
from load_game import Loader,STATUS
out=Path('build/arch-stage2b')
normal=Path('build/mario-castle-sdram-direct-packed-mul.package.json')
sof=Path('build/quartus-arch-stage2b/ArchStage2BSoC.sof')
qt='C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe'
if not sof.exists():raise RuntimeError('No timing-passing candidate SOF')
if 'minimum slack' not in Path('build/dma-quartus.log').read_text():raise RuntimeError('Timing gate did not pass')
with (out/'programming.log').open('w') as log:
 subprocess.run([qt,'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
loader=Loader()
try:
 status=loader.operation(STATUS,retries=40)
 if status['gpu_features']!=7:raise RuntimeError('Wrong candidate capabilities '+str(status))
 (out/'programmed-image.json').write_text(json.dumps({'sof':str(sof),'sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'status':status},indent=2)+'\n')
finally:loader.close()
for label,stem,instrumented in (
 ('packed-normal','mario-castle-sdram-direct-packed-mul',False),
 ('dma-normal','mario-castle-sdram-direct-dma-mul',False),
 ('packed-detail','mario-castle-sdram-direct-profile-detail-packed-mul',True),
 ('dma-detail','mario-castle-sdram-direct-profile-detail-dma-mul',True)):
 print('MEASURE',label,flush=True)
 collect(Path('build')/(stem+'.package.json'),Path('build')/(stem+'.symbols.json'),normal,out/('physical-'+label+'.json'),trials=3,instrumented=instrumented,reuse_immutable_assets=True)
 print('PASS',label,flush=True)
print('All physical cases finished; normal packed Mario restored',flush=True)
