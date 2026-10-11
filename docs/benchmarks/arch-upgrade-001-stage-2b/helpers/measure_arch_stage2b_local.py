from pathlib import Path
import sys
sys.path.insert(0,str(Path('scripts').resolve()))
from profile_cpu import collect
normal=Path('build/mario-castle-sdram-direct-packed-mul.package.json')
for label,stem,instrumented in (
 ('dma-local-normal','mario-castle-sdram-direct-dma-mul',False),
 ('dma-local-detail','mario-castle-sdram-direct-profile-detail-dma-mul',True)):
 print('MEASURE',label,flush=True)
 collect(Path('build')/(stem+'.package.json'),Path('build')/(stem+'.symbols.json'),normal,Path('build/arch-stage2b')/('physical-'+label+'.json'),trials=3,instrumented=instrumented,reuse_immutable_assets=True)
 print('PASS',label,flush=True)
