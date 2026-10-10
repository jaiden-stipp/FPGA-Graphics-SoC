from pathlib import Path
import subprocess,re,json,hashlib
qdir=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
for size in (8,16,32):
 name=f'CacheLine{size}SoC';out=f'build/quartus-line{size}'
 q=Path('docs/benchmarks/cache-lines-001/template.qsf').read_text().replace('build/quartus-burst',out)
 q+=f'\nset_parameter -name CACHE_LINE_BYTES {size}\n'
 Path('build/'+name+'.qsf.snapshot').write_text(q)
 Path(name+'.qsf').write_text(q);Path(name+'.qpf').write_text(f'QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "{name}"\n')
 for stage in ('map','fit','sta','asm'):
  with Path(f'build/line{size}-quartus-{stage}.log').open('w') as f:
   p=subprocess.run([str(qdir/f'quartus_{stage}.exe'),name],stdout=f,stderr=subprocess.STDOUT)
  print(size,stage,p.returncode,flush=True)
  if p.returncode:raise SystemExit(p.returncode)
  if stage=='sta':
   slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',Path(out+'/'+name+'.sta.summary').read_text())]
   if not slacks or min(slacks)<0:raise SystemExit('Timing failed; candidate not assembled')
 print(size,'sha256',hashlib.sha256(Path(out+'/'+name+'.sof').read_bytes()).hexdigest(),flush=True)
