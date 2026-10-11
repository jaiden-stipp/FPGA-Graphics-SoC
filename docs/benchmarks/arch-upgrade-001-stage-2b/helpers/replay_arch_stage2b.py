from pathlib import Path
import subprocess,sys
for name in ('castle','quake','fixtures'):
 out=Path('build/arch-stage2b')/(name+'-dma')
 with (Path('build/arch-stage2b')/(name+'-replay.log')).open('w') as log:
  subprocess.run([sys.executable,'scripts/replay_render_route.py','--out',str(out),'--capture-only','--dma','--simulate'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([sys.executable,'scripts/compare_render_frames.py',str(Path('build/arch-stage2a')/(name+'-packed')),str(out),'--out',str(Path('build/arch-stage2b')/(name+'-comparison.json'))],check=True)
 print('PASS final DMA',name,flush=True)
