from pathlib import Path
import subprocess
bin=Path('C:/intelFPGA/18.1/modelsim_ase/win32aloem');lib='build/burst-aligned'
for tb,g,name in [('sdram_memory_tb','-gBURST_ENABLED=0','memory-single'),('sdram_memory_tb','-gCACHE_ENABLED=0','memory-uncached'),('sdram_cache_tb','-gBURST_ENABLED=0','cache-single')]:
 p=subprocess.run([str(bin/'vsim.exe'),'-c','-L','altera_mf','-lib',lib,tb,g,'-do','onerror {quit -code 1}; run -all; quit -code 0'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 Path('build/burst-'+name+'.log').write_text(p.stdout);print(p.stdout[-950:])
 if p.returncode or '** Fatal:' in p.stdout or 'PASS '+tb not in p.stdout:raise SystemExit(1)
