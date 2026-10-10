from pathlib import Path
import subprocess,re
root=Path.cwd();q=Path('ProjectionSoC.qsf').read_text().replace('build/quartus-projection','build/quartus-burst')
q+='\nset_parameter -name ENABLE_CACHE 1\nset_parameter -name ENABLE_BURST 1\n'
Path('BurstSoC.qsf').write_text(q);Path('BurstSoC.qpf').write_text('QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "BurstSoC"\n')
bin=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
for stage in ('map','fit','sta','asm'):
 with Path('build/burst-quartus-'+stage+'.log').open('w') as out:
  p=subprocess.run([str(bin/('quartus_'+stage+'.exe')),'BurstSoC'],stdout=out,stderr=subprocess.STDOUT)
 print(stage,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
 if stage=='sta':
  text=Path('build/quartus-burst/BurstSoC.sta.summary').read_text();slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',text)]
  if not slacks or min(slacks)<0:raise SystemExit('Timing failed; stop before assembly/programming')
