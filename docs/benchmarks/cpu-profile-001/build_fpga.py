from pathlib import Path
import subprocess,re,hashlib
name='CpuProfileSoC';out='build/quartus-cpu-profile'
q=Path('docs/benchmarks/cache-lines-001/template.qsf').read_text().replace('build/quartus-burst',out)
q+='\nset_parameter -name CACHE_LINE_BYTES 32\nset_global_assignment -name SYSTEMVERILOG_FILE rtl/soc_cpu_counters.sv\n'
Path(name+'.qsf').write_text(q);Path(name+'.qpf').write_text(f'QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "{name}"\n')
Path('build/cpu-profile/project.qsf').write_text(q)
qdir=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
for stage in ('map','fit','sta','asm'):
    with Path(f'build/cpu-profile/quartus-{stage}.log').open('w') as f:
        result=subprocess.run([str(qdir/f'quartus_{stage}.exe'),name],stdout=f,stderr=subprocess.STDOUT)
    print(stage,result.returncode,flush=True)
    if result.returncode:raise SystemExit(result.returncode)
    if stage=='sta':
        slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',Path(out+'/'+name+'.sta.summary').read_text())]
        if not slacks or min(slacks)<0:raise SystemExit('Timing failed; do not program')
print('sof_sha256',hashlib.sha256(Path(out+'/'+name+'.sof').read_bytes()).hexdigest(),flush=True)
