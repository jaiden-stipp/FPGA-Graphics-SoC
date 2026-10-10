from pathlib import Path
import subprocess,re,hashlib
out=Path('build/integer-mul');out.mkdir(parents=True,exist_ok=True)
name='IntegerMulSoC';fit='build/quartus-integer-mul'
q=Path('docs/benchmarks/cache-lines-001/template.qsf').read_text().replace('build/quartus-burst',fit)
q+='\nset_parameter -name CACHE_LINE_BYTES 32\nset_global_assignment -name SYSTEMVERILOG_FILE rtl/soc_cpu_counters.sv\nset_global_assignment -name SYSTEMVERILOG_FILE rtl/soc_alu.sv\nset_global_assignment -name SYSTEMVERILOG_FILE rtl/generated/soc_ControlUnit.sv\n'
Path(name+'.qsf').write_text(q);Path(name+'.qpf').write_text(f'QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "{name}"\n');(out/'project.qsf').write_text(q)
qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
for stage in ('map','fit','sta','asm'):
 with (out/('quartus-'+stage+'.log')).open('w') as f:r=subprocess.run([str(qt/('quartus_'+stage+'.exe')),name],stdout=f,stderr=subprocess.STDOUT)
 print(stage,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
 if stage=='sta':
  slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',Path(fit+'/'+name+'.sta.summary').read_text())]
  print('minimum slack',min(slacks),flush=True)
  if not slacks or min(slacks)<0:raise SystemExit('Timing failed; not safe to program')
print('sof_sha256',hashlib.sha256(Path(fit+'/'+name+'.sof').read_bytes()).hexdigest(),flush=True)
