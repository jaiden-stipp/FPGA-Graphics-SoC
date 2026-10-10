import json,subprocess,time,sys,hashlib
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,BEGIN,READ,package_segments
mode=sys.argv[1];sof=Path(sys.argv[2]);result=Path('build/burst-board-'+mode+'.json')
expected={'baseline':'8326b76009f681087f3615256ff45f7f7bb5922dc43dfebca2d77387f499105b'}
assert sof.exists()
if mode in expected:assert hashlib.sha256(sof.read_bytes()).hexdigest()==expected[mode]
# Validate the complete Mario restore package before replacing the FPGA image.
restore=package_segments(Path('build/mario-castle-sdram-direct.package.json'))
probe=Path('build/burst-benchmark.bin').read_bytes();probe=probe.ljust((len(probe)+3)//4*4,b'\0')
report={'mode':mode,'sof_sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(probe).hexdigest(),'method':'Physical CPU cycle counter; same benchmark binary, 64 cold lines, 512 warm words, 512 deliberate conflict misses; not game FPS','samples':[]}
pgm=Path('C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe')
with Path('build/burst-program-'+mode+'.log').open('w') as f:p=subprocess.run([str(pgm),'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=f,stderr=subprocess.STDOUT)
if p.returncode:raise RuntimeError('FPGA programming failed')
l=Loader();attempt=False
try:
 for sample in range(3):
  attempt=True;l.transfer([(0,probe,'temporary burst-fill benchmark')])
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   status=l.operation(STATUS)
   if status['scratch']==0xdeadb017:raise RuntimeError('Probe integrity failure')
   if status['scratch']==0xb017600d:break
   time.sleep(.05)
  else:raise TimeoutError('Benchmark timed out')
  l.operation(BEGIN)
  values=[]
  for address in range(0x288,0x2cc,12):
   count=min(3,(0x2cc-address)//4);values.extend(l.operation(READ,address,count=count)['words'])
  errors,clock=values[:2];phases=[]
  for j,name in enumerate(('cold_lines','warm_words','conflict_lines')):
   phases.append(dict(zip(('cycles','hits','misses','fill_words','sum'),values[2+j*5:7+j*5]),name=name))
  expected_sums=[sum(0x12340000+8*i for i in range(64))&0xffffffff,sum(0x12340000+i for i in range(512))&0xffffffff,4*sum(0x12340000+0xabcd0000+16*i for i in range(64))&0xffffffff]
  assert errors==0 and clock==50000000
  for phase,checksum,counts in zip(phases,expected_sums,((0,64),(512,0),(0,512))):
   assert phase['sum']==checksum,(phase,checksum)
   assert (phase['hits'],phase['misses'])==counts,phase
   assert phase['fill_words']==8*phase['misses'],phase
  report['samples'].append({'errors':errors,'clock_hz':clock,'phases':phases});result.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['samples'][-1]),flush=True)
finally:
 if attempt:
  print('Restoring full Mario CPU and SDRAM assets',flush=True);l.transfer(restore);report['restored']=l.operation(STATUS)
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   status=l.operation(STATUS)
   if status['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Mario boot failed')
   if 0<status['scratch']<0x10000000:break
   time.sleep(.05)
  else:raise TimeoutError('Restored Mario did not complete a frame')
  report['restored_first_frame']=status
 l.close();result.write_text(json.dumps(report,indent=2)+'\n')
