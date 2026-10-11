from pathlib import Path
import subprocess, re, shutil

out=Path('build/screen-edges');out.mkdir(parents=True,exist_ok=True)
for stem in ('mario-castle-sdram-direct-mul','mario-castle-sdram-direct-profile-detail-mul'):
    for source in Path('build').glob(stem+'.*'):
        dest=out/'baseline'/source.name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copyfile(source,dest)
name='ScreenEdgesSoC';fit='build/quartus-screen-edges'
q=Path('docs/benchmarks/integer-mul-001/project.qsf').read_text().replace('build/quartus-integer-mul',fit).replace('external/renderer/rtl/pipeline/renderer.sv','rtl/generated/renderer.sv')
created=[]
try:
    for suffix,contents in [('qsf',q),('qpf','QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "ScreenEdgesSoC"\n')]:
        p=Path(name+'.'+suffix)
        if p.exists():raise RuntimeError('Refusing to overwrite '+str(p))
        p.write_text(contents);created.append(p)
    (out/'project.qsf').write_text(q)
    qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
    for stage in ('map','fit','sta','asm'):
        with (out/('quartus-'+stage+'.log')).open('w') as log:
            result=subprocess.run([str(qt/('quartus_'+stage+'.exe')),name],stdout=log,stderr=subprocess.STDOUT)
        print(stage,result.returncode,flush=True)
        if result.returncode:raise SystemExit(result.returncode)
        if stage=='sta':
            slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',Path(fit+'/'+name+'.sta.summary').read_text())]
            print('minimum reported slack',min(slacks),flush=True)
            if not slacks or min(slacks)<0:raise SystemExit('Timing failed; do not program')
finally:
    for p in created:p.unlink()
