"""Fit selectable depth precision against the accepted Stage 5 architecture."""
from pathlib import Path
import argparse,re,subprocess
import soc
def build(mode):
    soc.generate();root=soc.ROOT
    name={'depth12':'RenderDepth12SoC','subpixel':'RenderSubpixelSoC','depth8':'RenderDepth8SoC'}[mode]
    fit='build/quartus-render-'+mode;out=root/'build/render-fixes'/mode;out.mkdir(parents=True,exist_ok=True)
    q=(root/'docs/benchmarks/arch-upgrade-001-stage-5/project.qsf').read_text() if (root/'docs/benchmarks/arch-upgrade-001-stage-5/project.qsf').exists() else (root/'build/arch-stage5/worker/project.qsf').read_text()
    q=q.replace('build/quartus-arch-stage5-worker',fit).replace('external/renderer/rtl/pipeline/depth_test_stage.sv','rtl/generated/depth_test_stage.sv')
    if mode in ('depth12','subpixel'):q+='set_global_assignment -name VERILOG_MACRO "SOC_DEPTH12=1"\n'
    if mode=='subpixel':q+='set_global_assignment -name VERILOG_MACRO \"SOC_SUBPIXEL_DEPTH=1\"\n'
    created=[]
    try:
        for ext,body in [('qsf',q),('qpf','QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "'+name+'"\n')]:
            p=root/(name+'.'+ext)
            if p.exists():raise RuntimeError('Existing project '+str(p))
            p.write_text(body);created.append(p)
        (out/'project.qsf').write_text(q)
        qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
        for stage in ('map','fit','sta','asm'):
            with (out/('quartus-'+stage+'.log')).open('w') as log:
                subprocess.run([str(qt/('quartus_'+stage+'.exe')),name],cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
            print(mode,stage,'pass',flush=True)
            if stage=='sta':
                from measure_pixel_lanes import timing_gate
                timing_gate(root/fit,name)
    finally:
        for p in created:p.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('depth12','depth8','subpixel'));build(p.parse_args().mode)
