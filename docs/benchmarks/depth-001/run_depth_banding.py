import subprocess
from pathlib import Path
root=Path.cwd();out=root/'build/depth-banding';bin=Path('C:/intelFPGA/18.1/modelsim_ase/win32aloem')
commands=[['vlib','work'],['vlog','-sv','+incdir+'+str(root/'external/renderer/rtl/common'),'+incdir+'+str(root/'external/renderer/rtl/generated'),str(root/'external/renderer/rtl/common/iterative_signed_divider.sv'),str(root/'external/renderer/rtl/pipeline/depth_test_stage.sv'),str(root/'external/renderer/rtl/pipeline/renderer.sv'),str(root/'build/depth_banding_tb.sv')],['vsim','-c','work.depth_banding_tb','-do','run -all; quit -f']]
for n,c in enumerate(commands):
 p=subprocess.run([str(bin/c[0]),*c[1:]],cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/(str(n)+'.log')).write_text(p.stdout);print(p.stdout[-1800:]);
 if p.returncode or 'Fatal:' in p.stdout or '** Error' in p.stdout:raise SystemExit(1)
