import sys,time,json,binascii
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,BEGIN,READ,package_segments
segments=package_segments(Path('build/mario-castle-sdram.package.json'))
restore=[s for s in segments if s[0]==0]
assets=[s for s in segments if s[0]==0x80000000][0][1]
assert len(assets)==883124
probe=Path('build/sdram-read-probe.bin').read_bytes();probe=probe.ljust((len(probe)+3)//4*4,b'\0')
report={'expected_crc16':binascii.crc_hqx(assets,0xffff),'bytes':len(assets)}
l=Loader();attempt=False
try:
 report['before']=l.operation(STATUS);attempt=True
 l.transfer([(0,probe,'temporary SDRAM CPU read probe')])
 deadline=time.monotonic()+55
 while time.monotonic()<deadline:
  status=l.operation(STATUS)
  if status['scratch']&0xffff0000==0xcace0000:break
  time.sleep(.2)
 report['completed']=status['scratch']&0xffff0000==0xcace0000
 l.operation(BEGIN)
 values=list(l.operation(READ,0x250,count=3)['words'])+[l.operation(READ,0x25c,count=1)['words'][0]]
 report.update(dict(zip(['cache_abi','errors','words','crc16'],values)))
 report['pass']=report['completed'] and report['errors']==0 and report['words']==len(assets)//4 and report['crc16']==report['expected_crc16']
 print(json.dumps(report),flush=True)
finally:
 if attempt:
  l.transfer(restore);report['restored']=l.operation(STATUS)
 l.close();Path('build/sdram-cpu-read-probe.json').write_text(json.dumps(report,indent=2)+'\n')
