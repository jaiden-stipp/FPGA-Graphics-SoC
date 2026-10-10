from pathlib import Path
import subprocess,sys,re,json,time
root=Path.cwd();py=sys.executable
summary=Path('build/quartus-burst/BurstSoC.sta.summary').read_text();slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary)]
assert slacks and min(slacks)>=0,'Candidate timing failure'
log=Path('build/burst-aligned-tests.log').read_text()+Path('build/burst-aligned-cpu-tests.log').read_text()
for name in ('sdram_cache_tb','sdram_memory_tb','sdram_cpu_tb','udp_loader_tb','soc_memory_tb','soc_mmio_tb'):assert 'PASS '+name in log,name
assert Path('build/quartus-burst/BurstSoC.sof').stat().st_mtime>=max(p.stat().st_mtime for p in Path('rtl').glob('sdram*.sv'))
p=subprocess.run([py,'build/measure_burst_board.py','candidate','build/quartus-burst/BurstSoC.sof'])
if p.returncode:
 print('Candidate measurement failed; restoring preserved baseline FPGA image and Mario',flush=True)
 pgm='C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe'
 subprocess.run([pgm,'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;build/quartus-projection/ProjectionSoC.sof@1'],check=True)
 sys.path.insert(0,'scripts');from load_game import Loader,package_segments
 l=Loader()
 try:l.transfer(package_segments(Path('build/mario-castle-sdram-direct.package.json')))
 finally:l.close()
 raise SystemExit(p.returncode)
