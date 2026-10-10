from pathlib import Path
import sys,subprocess,hashlib,json,re,time
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,BEGIN,package_segments
from profile_cpu import collect,read_words
out=Path('build/integer-mul')
old=Path('build/quartus-line32/CacheLine32SoC.sof').resolve();new=Path('build/quartus-integer-mul/IntegerMulSoC.sof').resolve()
assert hashlib.sha256(new.read_bytes()).hexdigest()=='84de9a3059e5a40957438df348da434c05e462955e60528491f2f2ac6713484b'
assert min(float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',new.with_suffix('.sta.summary').read_text()))>=0
baseline=Path('build/cpu-profile/baseline/mario-castle-sdram-direct.package.json')
probe=out/'mul-probe.bin';symbols=json.loads((out/'mul-probe.symbols.json').read_text())
pgm='C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe'
def program(sof,label):
 with (out/(label+'-program.log')).open('w') as f:subprocess.run([pgm,'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=f,stderr=subprocess.STDOUT,check=True)
def wait_game(loader):
 deadline=time.monotonic()+30
 while time.monotonic()<deadline:
  status=loader.operation(STATUS)
  if status['scratch']&0xffff0000==0xdead0000:raise RuntimeError('startup failure '+str(status))
  if status['initialized'] and not status['held'] and 0<status['scratch']<0x10000000:return status
  time.sleep(.05)
 raise RuntimeError('Game failed to start')
r={'baseline_revision':'af8580f','candidate_revision':'cdf0f8c','sof_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(probe.read_bytes()).hexdigest(),'probe_trials':[],'cases':[]}
success=False
try:
 program(new,'candidate')
 loader=Loader()
 try:
  for trial in range(3):
   loader.transfer([(0,probe.read_bytes(),probe.name)])
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    status=loader.operation(STATUS)
    if status['scratch']==0x6d750100:break
    if status['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Probe failure '+str(status))
    time.sleep(.01)
   else:raise RuntimeError('Probe timed out')
   loader.operation(BEGIN)
   values={name:read_words(loader,symbols[name],1)[0] for name in ('mul_probe_done','mul_probe_cycles','software_probe_cycles','mul_probe_hash')}
   assert values['mul_probe_done']==256
   r['probe_trials'].append(values);print('probe',trial+1,values,flush=True)
 finally:loader.close()
 for label,stem,moving,instrumented in [('software-standing','mario-castle-sdram-direct-profile-detail',False,True),('mul-standing','mario-castle-sdram-direct-profile-detail-mul',False,True),('mul-moving','mario-castle-sdram-direct-profile-detail-mul',True,True),('mul-unprofiled-standing','mario-castle-sdram-direct-mul',False,False)]:
  print('BEGIN',label,flush=True)
  collect(Path('build/'+stem+'.package.json'),Path('build/'+stem+'.symbols.json'),baseline,out/(label+'.json'),trials=3,moving=moving,instrumented=instrumented,reuse_immutable_assets=True)
  r['cases'].append(label)
 print('Loading unprofiled MUL Mario on the candidate FPGA',flush=True)
 loader=Loader()
 try:
  loader.transfer(package_segments(Path('build/mario-castle-sdram-direct-mul.package.json')))
  a=wait_game(loader);time.sleep(.25);b=loader.operation(STATUS);assert b['scratch']>a['scratch']
  r['deployed_status']=[a,b];success=True
 finally:loader.close()
except Exception as exc:r['failure']=repr(exc);raise
finally:
 if not success:
  print('Restoring original FPGA and game after failed experiment',flush=True);program(old,'restore')
  loader=Loader()
  try:loader.transfer(package_segments(baseline));r['restored_status']=wait_game(loader)
  finally:loader.close()
 (out/'experiment.json').write_text(json.dumps(r,indent=2)+'\n')
