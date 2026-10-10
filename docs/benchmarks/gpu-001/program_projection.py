import sys,json,time,subprocess,hashlib,re
from pathlib import Path
sys.path.insert(0,'scripts')
from load_game import Loader,STATUS,package_segments,require_hardware
candidate=Path('build/quartus-projection/ProjectionSoC.sof');rollback=Path('build/quartus-cache/CacheSoC.sof')
summary=Path('build/quartus-projection/ProjectionSoC.sta.summary')
assert candidate.is_file() and rollback.is_file()
assert candidate.stat().st_mtime>Path('rtl/generated/transform_3d_pipeline.sv').stat().st_mtime
slack=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary.read_text())]
assert slack and min(slack)>=0,'Timing failed: programming forbidden'
package=Path('build/mario-castle-sdram-direct.package.json');baseline=Path('build/mario-castle-sdram.package.json')
trial_segments=package_segments(package);restore_segments=package_segments(baseline)
assert [(a,d) for a,d,_ in trial_segments if a>=0x80000000]==[(a,d) for a,d,_ in restore_segments if a>=0x80000000]
pgm=Path(r'C:\intelFPGA_lite\18.1\quartus\bin64\quartus_pgm.exe')
report={'candidate_sof_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'rollback_sof_sha256':hashlib.sha256(rollback.read_bytes()).hexdigest(),'package':str(package),'minimum_reported_slack_ns':min(slack)}
def program(path,label):
 cmd=[str(pgm),'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(path)+'@1']
 r=subprocess.run(cmd,capture_output=True,text=True);Path(f'build/projection-program-{label}.log').write_text(r.stdout+r.stderr);print(r.stdout[-1800:],flush=True)
 if r.returncode:raise RuntimeError(f'Programming {label} failed ({r.returncode})')
def load(segments,spec):
 l=Loader()
 try:
  require_hardware(l,spec);l.transfer(segments)
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   s=l.operation(STATUS)
   if s['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Game startup failed')
   if 0<s['scratch']<0x10000000:return s
   time.sleep(.05)
  raise TimeoutError('No completed game frame')
 finally:l.close()
attempt=False
try:
 attempt=True;program(candidate,'candidate')
 report['running']=load(trial_segments,json.loads(package.read_text()));report['left_running']='projection correction with direct-terrain Mario diagnostic'
except BaseException as error:
 report['error']=str(error)
 if attempt:
  program(rollback,'rollback');report['restored']=load(restore_segments,json.loads(baseline.read_text()))
 raise
finally:
 Path('build/projection-board.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report),flush=True)
