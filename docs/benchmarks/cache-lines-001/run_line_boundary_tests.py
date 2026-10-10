import subprocess
from pathlib import Path
b=Path('C:/intelFPGA/18.1/modelsim_ase/win32aloem');lib='build/line-simlib'
p=subprocess.run([str(b/'vlog.exe'),'-work',lib,'-sv','sim/sdram_memory_tb.sv'],capture_output=True,text=True)
if p.returncode:print(p.stdout,p.stderr);raise SystemExit(p.returncode)
for size in (32,16,8):
 for burst in (1,0):
  p=subprocess.run([str(b/'vsim.exe'),'-c','-L','altera_mf','-lib',lib,'sdram_memory_tb',f'-gCACHE_LINE_BYTES={size}',f'-gBURST_ENABLED={burst}','-do','onerror {quit -code 1}; run -all; quit -code 0'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  Path(f'build/line-{size}-sdram_memory_tb-burst{burst}.log').write_text(p.stdout)
  print(size,burst,p.stdout[-650:],flush=True)
  if p.returncode or '** Fatal:' in p.stdout or 'PASS sdram_memory_tb' not in p.stdout:raise SystemExit(1)
