from pathlib import Path
import sys,subprocess
sys.path.insert(0,'scripts');import soc
s=Path('CacheSoC.qsf').read_text()
s=soc.replace_once(s,'build/quartus-cache','build/quartus-projection')
s=soc.replace_once(s,'external/renderer/rtl/pipeline/transform_3d_pipeline.sv','rtl/generated/transform_3d_pipeline.sv')
Path('ProjectionSoC.qsf').write_text(s);Path('ProjectionSoC.qpf').write_text('QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "ProjectionSoC"\n')
bin=Path(r'C:\intelFPGA_lite\18.1\quartus\bin64')
for stage in ('map','fit','sta','asm'):
 with Path(f'build/projection-quartus-{stage}.log').open('w') as out:
  r=subprocess.run([str(bin/f'quartus_{stage}.exe'),'ProjectionSoC'],stdout=out,stderr=subprocess.STDOUT)
 print(stage,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
 if stage=='sta':
  import re
  summary=Path('build/quartus-projection/ProjectionSoC.sta.summary').read_text()
  slack=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary)]
  if not slack or min(slack)<0:raise SystemExit('Timing failed; candidate must not be programmed')
