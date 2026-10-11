from pathlib import Path
import subprocess,sys,shutil
sys.path.insert(0,'scripts')
import soc
soc.generate()
root=Path('build/arch-stage3')
for mode in ('serial','overlap'):
 for name in ('castle','quake','fixtures'):
  before=Path('build/arch-stage2a')/(name+'-packed')
  out=root/(name+'-'+mode);out.mkdir(parents=True,exist_ok=True)
  for f in ('input.hex','input.meta','input.json'):shutil.copyfile(before/f,out/f)
  with (root/(name+'-'+mode+'-replay.log')).open('w') as log:
   subprocess.run([sys.executable,'scripts/replay_render_route.py','--out',str(out),'--capture-only','--packed-mmio','--simulate']+(['--setup-overlap'] if mode=='overlap' else []),stdout=log,stderr=subprocess.STDOUT,check=True)
  subprocess.run([sys.executable,'scripts/compare_render_frames.py',str(before),str(out),'--out',str(root/(name+'-'+mode+'-comparison.json'))],check=True)
  print('PASS',name,mode,flush=True)
