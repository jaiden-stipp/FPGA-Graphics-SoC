from pathlib import Path
import subprocess,sys
sys.path.insert(0,'scripts');import soc
b=Path('C:/intelFPGA/18.1/modelsim_ase/win32aloem');lib=Path('build/line-simlib');lib.mkdir(exist_ok=True)
def run(cmd):
 p=subprocess.run([str(x) for x in cmd],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 if p.returncode: print(p.stdout);raise SystemExit(p.returncode)
 return p.stdout
run([b/'vlib.exe',lib])
src=soc.sources(False)+[Path('sim/sdram_device_model.sv'),Path('sim/sdram_memory_tb.sv'),Path('sim/sdram_cache_tb.sv'),Path('sim/sdram_cpu_tb.sv'),Path('sim/udp_loader_tb.sv')]
log=run([b/'vlog.exe','-work',lib,'-sv','-mfcu','+incdir+external/renderer/rtl/common+sim/generated+sim',*src]);Path('build/line-compile.log').write_text(log)
for size in (32,16,8):
 for tb in ('sdram_memory_tb','sdram_cache_tb'):
  for burst in (1,0):
   log=run([b/'vsim.exe','-c','-L','altera_mf','-lib',lib,tb,f'-gCACHE_LINE_BYTES={size}',f'-gBURST_ENABLED={burst}','-do','onerror {quit -code 1}; run -all; quit -code 0'])
   Path(f'build/line-{size}-{tb}-burst{burst}.log').write_text(log)
   print(size,tb,burst,log[-750:],flush=True)
   if 'PASS '+tb not in log or '** Fatal:' in log:raise SystemExit(1)
for tb,size in [('sdram_cpu_tb',n) for n in (32,16,8)]+[('udp_loader_tb',32)]:
 log=run([b/'vsim.exe','-c','-L','altera_mf','-lib',lib,tb,*([f'-gCACHE_LINE_BYTES={size}'] if tb=='sdram_cpu_tb' else []),'-do','onerror {quit -code 1}; run -all; quit -code 0'])
 Path(f'build/line-{size}-{tb}.log').write_text(log)
 if 'PASS '+tb not in log or '** Fatal:' in log:print(log);raise SystemExit(1)
 print(log[-500:],flush=True)
