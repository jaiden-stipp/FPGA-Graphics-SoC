import subprocess
from pathlib import Path
bin=Path(r'C:\intelFPGA\18.1\modelsim_ase\win32aloem');lib=Path('build/projection-baseline-sim')
commands=[[str(bin/'vlib.exe'),str(lib)],[str(bin/'vlog.exe'),'-work',str(lib),'-sv','-mfcu','+incdir+external/renderer/rtl/common','external/renderer/rtl/common/iterative_signed_divider.sv','external/renderer/rtl/pipeline/transform_3d_pipeline.sv','sim/projection_precision_tb.sv'],[str(bin/'vsim.exe'),'-c','-lib',str(lib),'projection_precision_tb','-gREQUIRE_ACCURACY=0','-do','onerror {quit -code 1}; run -all; quit -code 0']]
for i,cmd in enumerate(commands):
 r=subprocess.run(cmd,capture_output=True,text=True);Path(f'build/projection-baseline-{i}.log').write_text(r.stdout+r.stderr);print(r.stdout[-3500:],r.stderr,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
