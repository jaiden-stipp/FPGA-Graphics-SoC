"""Stage 3 physical resident-geometry fixture and matched standing-game profiles."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from load_game import Loader, STATUS, BEGIN, package_segments, require_hardware
from profile_cpu import collect, read_words, GPU
from soc import ROOT

OUT = ROOT / 'build/arch-stage3'
NORMAL = ROOT / 'build/mario-castle-sdram-direct-packed-mul.package.json'
DETAIL = ROOT / 'build/mario-castle-sdram-direct-profile-detail-packed-mul.package.json'


def build_probe():
    out=OUT/'probe';out.mkdir(parents=True,exist_ok=True)
    llvm=Path('C:/Program Files/LLVM/bin');elf=out/'probe.elf'
    cmd=[str(llvm/'clang.exe'),'--target=riscv32-unknown-elf','-fuse-ld=lld',
        '-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax','-O1',
        '-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror',
        '-DGFX_PACKED','-ffunction-sections','-fdata-sections','-Ifirmware/include',
        '-Ifirmware/generated','-Wl,-T,firmware/link.ld','-Wl,--no-relax',
        '-Wl,--gc-sections','-Wl,-Map,'+str(out/'probe.map'),
        'firmware/start.S','firmware/tests/setup_overlap_probe.c',
        'firmware/src/gfx.c','firmware/src/gfx_scene.c','-o',str(elf)]
    subprocess.run(cmd,cwd=ROOT,check=True)
    subprocess.run([str(llvm/'llvm-objcopy.exe'),'-O','binary',str(elf),str(out/'probe.bin')],check=True)
    nm=subprocess.check_output([str(llvm/'llvm-nm.exe'),'--defined-only',str(elf)],text=True)
    syms={m[3]:int(m[1],16) for line in nm.splitlines() if (m:=re.fullmatch(r'([0-9a-fA-F]+)\s+(\w)\s+(\S+)',line))}
    dis=subprocess.check_output([str(llvm/'llvm-objdump.exe'),'-d',str(elf)],text=True)
    (out/'probe-disassembly.txt').write_text(dis)
    for line in dis.splitlines():
        m=re.match(r'\s*[0-9a-f]+:\s+((?:[0-9a-f]{2} ){3}[0-9a-f]{2})',line)
        if m:
            ins=int.from_bytes(bytes.fromhex(m[1]),'little')
            if ins&0x7f==0x33 and ins>>25==1:
                raise ValueError('Probe unexpectedly emits M instructions')
    data=(out/'probe.bin').read_bytes()
    spec={'format':'soc-game-package','version':1,'required_gpu_features':{'packed-enqueue-v1':True},
          'segments':[{'file':'probe.bin','address':0,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
    (out/'probe.package.json').write_text(json.dumps(spec,indent=2)+'\n')
    (out/'build.json').write_text(json.dumps({'symbols':syms,'compile_command':cmd,'package':spec},indent=2)+'\n')


def probe(mode):
    out=OUT/'probe';syms=json.loads((out/'build.json').read_text())['symbols']
    report={'scope':'Synthetic resident indexed meshes: 128 repeated faces at three projected sizes; unchanged packed firmware; three resets per image. GPU total includes clear and VGA wait. raster_cycles is busy-union, not exclusive traversal.', 'trials':[]}
    loader=Loader()
    try:
        require_hardware(loader,json.loads((out/'probe.package.json').read_text()))
        for trial in range(3):
            loader.transfer(package_segments(out/'probe.package.json'))
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                status=loader.operation(STATUS)
                if status['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Probe failure '+str(status))
                if status['scratch']==0x3300600d:break
                time.sleep(.02)
            else:raise TimeoutError('Stage 3 GPU probe timeout')
            loader.operation(BEGIN)
            values=read_words(loader,syms['setup_results'],42)
            if read_words(loader,syms['setup_clock'],1)[0]!=50000000:raise RuntimeError('Wrong clock')
            rows=[]
            for mesh in range(3):
                row=dict(zip(GPU,values[mesh*14:mesh*14+13]));row['frame']=values[mesh*14+13]
                if (row['frame']!=mesh+1 or row['triangles_submitted']!=128 or
                    row['triangles_culled'] or not row['bounding_box_pixels'] or not row['pixels_written']):
                    raise RuntimeError('Fixture count/frame/coverage mismatch')
                rows.append(row)
            report['trials'].append({'trial':trial+1,'raw_words':values,'meshes':rows,'status':status})
            print(mode,'probe',trial+1,[(r['raster_cycles'],r['total_cycles']-r['swap_wait_cycles']) for r in rows],flush=True)
    finally:
        loader.close()
        (OUT/('physical-'+mode+'-probe.json')).write_text(json.dumps(report,indent=2)+'\n')


def program(mode):
    name='ArchStage3SerialSoC' if mode=='serial' else 'ArchStage3SoC'
    fit=ROOT/('build/quartus-arch-stage3-'+mode)
    summary=(fit/(name+'.sta.summary')).read_text()
    slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary)]
    if not slacks or min(slacks)<0:raise RuntimeError('Timing gate failed')
    sof=fit/(name+'.sof')
    with (OUT/(mode+'-programming.log')).open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe',
            '-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        status=loader.operation(STATUS,retries=40)
        if status['gpu_features']!=3:raise RuntimeError('DMA must stay disabled')
        (OUT/(mode+'-programmed-image.json')).write_text(json.dumps({'sof':str(sof),'sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'status':status},indent=2)+'\n')
    finally:loader.close()


def restore_accepted():
    sof=ROOT/'build/quartus-arch-stage2a/ArchStage2ASoC.sof'
    expected='917ed067296ef2405c7d4706dea4224da261add9a9a481ff1e5c4b45d94c9a32'
    if hashlib.sha256(sof.read_bytes()).hexdigest()!=expected:raise RuntimeError('Accepted SOF changed')
    with (OUT/'rollback-programming.log').open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe',
            '-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        require_hardware(loader,json.loads(NORMAL.read_text()))
        loader.transfer(package_segments(NORMAL))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            first=loader.operation(STATUS)
            if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
            time.sleep(.05)
        else:raise RuntimeError('Accepted Mario did not resume')
        time.sleep(1);last=loader.operation(STATUS)
        if last['held'] or last['scratch']<=first['scratch'] or last['gpu_features']!=3:
            raise RuntimeError('Accepted image progress failed')
        (OUT/'final-running-check.json').write_text(json.dumps({'sof':str(sof),'sof_sha256':expected,
            'package':str(NORMAL),'segments':json.loads(NORMAL.read_text())['segments'],
            'first_status':first,'last_status':last},indent=2)+'\n')
    finally:loader.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-only',action='store_true')
    p.add_argument('--mode',choices=('both','serial','overlap'),default='both');a=p.parse_args()
    build_probe()
    if not a.build_only:
        # Never leave failed experiments selected on the physical board.
        try:
            for mode in ('serial','overlap') if a.mode=='both' else (a.mode,):
                program(mode);probe(mode)
                for label,package,instrumented in [('normal',NORMAL,False),('detail',DETAIL,True)]:
                    collect(package,package.with_name(package.name.replace('.package.json','.symbols.json')),
                        NORMAL,OUT/('physical-'+mode+'-'+label+'.json'),trials=3,
                        instrumented=instrumented,reuse_immutable_assets=True)
        finally:
            # Known accepted original image, full CPU/assets upload/readback.
            restore_accepted()
