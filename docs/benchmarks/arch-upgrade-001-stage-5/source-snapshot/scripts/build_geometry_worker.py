"""Stage 5 matched builds, retaining accepted Stage 4 raster/transport/clocks."""
import argparse
from pathlib import Path
import re,subprocess
import soc

def build(mode):
    soc.generate();root=soc.ROOT
    out=root/'build/arch-stage5'/mode;out.mkdir(parents=True,exist_ok=True)
    name='ArchStage5ControlSoC' if mode=='control' else 'ArchStage5SoC'
    fit='build/quartus-arch-stage5-'+mode
    q=(root/'docs/benchmarks/arch-upgrade-001-stage-4/dual/project.qsf').read_text()
    q=q.replace('build/quartus-arch-stage4-dual',fit)
    q+='set_global_assignment -name SYSTEMVERILOG_FILE rtl/geometry_worker.sv\n'
    if mode=='worker':q+='set_global_assignment -name VERILOG_MACRO "SOC_GEOMETRY_WORKER=1"\n'
    created=[]
    try:
        for suffix,contents in [('qsf',q),('qpf','QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "'+name+'"\n')]:
            p=root/(name+'.'+suffix)
            if p.exists():raise RuntimeError('Refusing to overwrite '+str(p))
            p.write_text(contents);created.append(p)
        (out/'project.qsf').write_text(q)
        qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
        for stage in ('map','fit','sta','asm'):
            with (out/('quartus-'+stage+'.log')).open('w') as log:
                result=subprocess.run([str(qt/('quartus_'+stage+'.exe')),name],cwd=root,stdout=log,stderr=subprocess.STDOUT)
            print(mode,stage,result.returncode,flush=True)
            if result.returncode:raise RuntimeError('Quartus failed '+stage)
            if stage=='sta':
                summary=(root/fit/(name+'.sta.summary')).read_text()
                slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary)]
                if not slacks or min(slacks)<0:raise RuntimeError('Timing failed; refusing assembly/deployment')
                print(mode,'minimum slack',min(slacks),flush=True)
    finally:
        for p in created:p.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('control','worker','both'));a=p.parse_args()
    for mode in ('worker','control') if a.mode=='both' else (a.mode,):build(mode)
