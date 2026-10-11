import json,sys,subprocess,shutil
from pathlib import Path
root=Path.cwd()
for kind in ('castle','quake','fixtures'):
 before=root/'build/arch-stage3'/(kind+'-overlap')
 after=root/'build/arch-stage4'/(kind+'-dual')
 after.mkdir(parents=True,exist_ok=True)
 for name in ('input.hex','input.meta','input.json'):shutil.copyfile(before/name,after/name)
 subprocess.run([sys.executable,'scripts/replay_render_route.py','--capture-only','--packed-mmio','--setup-overlap','--two-pixel-lanes','--out',str(after),'--simulate'],check=True)
 subprocess.run([sys.executable,'scripts/compare_render_frames.py',str(before),str(after),'--out',str(root/'build/arch-stage4'/(kind+'-comparison.json'))],check=True)
