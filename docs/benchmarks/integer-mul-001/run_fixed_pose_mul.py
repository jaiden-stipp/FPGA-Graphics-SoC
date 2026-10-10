import sys,json,time
from pathlib import Path
sys.path.insert(0,'scripts')
from profile_cpu import collect
from load_game import Loader,STATUS,package_segments
out=Path('build/integer-mul');restore=Path('build/mario-castle-sdram-direct-mul.package.json')
r={'fixture_revision':'762895b','scope':'Standing spawn view; original idle start pose held for identical render work; normal physics/camera/tick scheduling','cases':[]}
try:
 for name,stem in [('fixed-software','mario-castle-fixed-pose-software'),('fixed-mul','mario-castle-fixed-pose-mul')]:
  print('BEGIN',name,flush=True)
  collect(Path('build/'+stem+'.package.json'),Path('build/'+stem+'.symbols.json'),restore,out/(name+'.json'),trials=3,reuse_immutable_assets=True)
  r['cases'].append(name)
except Exception as exc:r['failure']=repr(exc);raise
finally:
 loader=Loader()
 try:
  loader.transfer(package_segments(restore));deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   a=loader.operation(STATUS)
   if a['initialized'] and not a['held'] and 0<a['scratch']<0x10000000:break
   time.sleep(.05)
  else:raise RuntimeError('MUL game did not resume')
  time.sleep(.25);b=loader.operation(STATUS);assert b['scratch']>a['scratch'];r['deployed_status']=[a,b]
 finally:loader.close();(out/'fixed-pose-experiment.json').write_text(json.dumps(r,indent=2)+'\n')
