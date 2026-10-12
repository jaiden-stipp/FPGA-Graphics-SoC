import sys,subprocess
from pathlib import Path
out=Path('build/arch-stage5')
for g in (0,1):
 subprocess.run([sys.executable,'scripts/replay_render_route.py','--capture-only','--packed-mmio','--setup-overlap','--two-pixel-lanes','--out',str(out/f'game-replay-{g}'),'--simulate'],check=True)
subprocess.run([sys.executable,'scripts/compare_render_frames.py',str(out/'game-replay-0'),str(out/'game-replay-1'),'--out',str(out/'gpu-comparison.json')],check=True)
