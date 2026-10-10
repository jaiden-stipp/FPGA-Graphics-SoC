import sys,subprocess
from pathlib import Path
sys.path.insert(0,'scripts');import soc
soc.generate()
bin=Path(r'C:\intelFPGA\18.1\modelsim_ase\win32aloem');lib=Path('build/projection-candidate-sim')
commands=[[str(bin/'vlib.exe'),str(lib)],[str(bin/'vlog.exe'),'-work',str(lib),'-sv','-mfcu','+incdir+external/renderer/rtl/common','external/renderer/rtl/common/iterative_signed_divider.sv','rtl/generated/transform_3d_pipeline.sv','sim/projection_precision_tb.sv','external/renderer/sim/transform_3d_tb.sv','external/renderer/sim/transform_clipping_tb.sv']]
for i,cmd in enumerate(commands):
 r=subprocess.run(cmd,capture_output=True,text=True);Path(f'build/projection-candidate-{i}.log').write_text(r.stdout+r.stderr);print(r.stdout[-1000:],r.stderr,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
for name in ('projection_precision_tb','transform_3d_tb','transform_clipping_tb'):
 r=subprocess.run([str(bin/'vsim.exe'),'-c','-lib',str(lib),name,'-do','onerror {quit -code 1}; run -all; quit -code 0'],capture_output=True,text=True);out=r.stdout+r.stderr;Path(f'build/projection-{name}.log').write_text(out);print(out[-2500:],flush=True)
 if r.returncode or '** Fatal:' in out or '** Error:' in out:raise SystemExit(1)
