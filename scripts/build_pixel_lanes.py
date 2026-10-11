"""Build matched Stage 3/control and Stage 4/two-lane images at unchanged clocks."""
import argparse
from pathlib import Path
import re
import subprocess
import soc


def build(mode):
    soc.generate()
    root=soc.ROOT
    out=root/'build/arch-stage4'/mode
    out.mkdir(parents=True,exist_ok=True)
    name='ArchStage4ControlSoC' if mode=='control' else 'ArchStage4SoC'
    fit='build/quartus-arch-stage4-'+mode
    q=(root/'docs/benchmarks/arch-upgrade-001-stage-2a/project.qsf').read_text()
    q=q.replace('build/quartus-arch-stage2a',fit)
    q=q.replace('external/renderer/rtl/video/vga_controller.sv','rtl/generated/vga_controller.sv')
    q=q.replace('external/renderer/rtl/pipeline/render_performance_counters.sv','rtl/generated/render_performance_counters.sv')
    for file in ('renderer_serial.sv','triangle_setup_engine.sv','renderer_overlap.sv',
                 'renderer_dual.sv','zbuffer_single.sv','framebuffer_single.sv',
                 'zbuffer_banked.sv','framebuffer_banked.sv','pixel_bank_ram.sv'):
        q+='set_global_assignment -name SYSTEMVERILOG_FILE rtl/generated/'+file+'\n'
    q+='set_global_assignment -name VERILOG_MACRO "SOC_DISABLE_COMMAND_DMA=1"\n'
    q+='set_global_assignment -name VERILOG_MACRO "SOC_GPU_SETUP_OVERLAP=1"\n'
    if mode=='dual':
        q+='set_global_assignment -name VERILOG_MACRO "SOC_GPU_TWO_PIXEL_LANES=1"\n'
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('control','dual','both'));a=p.parse_args()
    for mode in ('control','dual') if a.mode=='both' else (a.mode,):build(mode)
