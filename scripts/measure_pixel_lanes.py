"""Matched Stage 4 physical trials; always restore accepted Stage 3 Mario."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import measure_setup_overlap as fixture
from load_game import Loader, STATUS, package_segments, require_hardware
from profile_cpu import collect
from soc import ROOT

OUT=ROOT/'build/arch-stage4'
NORMAL=fixture.NORMAL
DETAIL=fixture.DETAIL
ACCEPTED=ROOT/'build/quartus-arch-stage3-overlap/ArchStage3SoC.sof'
ACCEPTED_SHA='eb28b7007c48fc799ec729655d83a823112ea15c73a06cac665c32e9f1037f62'


def timing_gate(fit,name):
    summary=(fit/(name+'.sta.summary')).read_text()
    slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',summary)]
    if not slacks or min(slacks)<0:raise RuntimeError('Timing gate failed')
    report=(fit/(name+'.sta.rpt')).read_text()
    for label in ('Clocks','Input Ports','Input Port Paths','Output Ports','Output Port Paths'):
        m=re.search(r';\s*Unconstrained '+label+r'\s*;\s*(\d+)\s*;\s*(\d+)\s*;',report)
        if not m or int(m[1]) or int(m[2]):raise RuntimeError('Constraint coverage failed: '+label)


def program(mode):
    name='ArchStage4ControlSoC' if mode=='control' else 'ArchStage4SoC'
    fit=ROOT/('build/quartus-arch-stage4-'+mode)
    timing_gate(fit,name)
    sof=fit/(name+'.sof')
    with (OUT/(mode+'-programming.log')).open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe',
            '-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        status=loader.operation(STATUS,retries=40)
        if status['gpu_features']!=3:raise RuntimeError('DMA must stay disabled')
        (OUT/(mode+'-programmed-image.json')).write_text(json.dumps({'sof':str(sof),
            'sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'status':status},indent=2)+'\n')
    finally:loader.close()


def restore_accepted():
    if hashlib.sha256(ACCEPTED.read_bytes()).hexdigest()!=ACCEPTED_SHA:raise RuntimeError('Accepted Stage 3 SOF changed')
    with (OUT/'rollback-programming.log').open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe',
            '-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(ACCEPTED)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        spec=json.loads(NORMAL.read_text());require_hardware(loader,spec)
        loader.transfer(package_segments(NORMAL))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            first=loader.operation(STATUS)
            if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
            time.sleep(.05)
        else:raise RuntimeError('Accepted Mario did not resume')
        time.sleep(1);last=loader.operation(STATUS)
        if last['held'] or last['scratch']<=first['scratch'] or last['gpu_features']!=3:
            raise RuntimeError('Accepted Stage 3 progress failed')
        (OUT/'final-running-check.json').write_text(json.dumps({'sof':str(ACCEPTED),
            'sof_sha256':ACCEPTED_SHA,'package':str(NORMAL),'segments':spec['segments'],
            'first_status':first,'last_status':last},indent=2)+'\n')
    finally:loader.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('both','control','dual'),default='both')
    p.add_argument('--build-only',action='store_true');a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    fixture.OUT=OUT;fixture.build_probe()
    old=ROOT/'build/arch-stage3/probe/probe.bin';new=OUT/'probe/probe.bin'
    if old.read_bytes()!=new.read_bytes():raise RuntimeError('Probe must be unchanged from Stage 3')
    if not a.build_only:
        # Exact replay equality is mandatory before programming either variant.
        for kind in ('castle','quake','fixtures'):
            if not json.loads((OUT/(kind+'-comparison.json')).read_text())['exact']:
                raise RuntimeError('Stage 4 replay gate failed')
        try:
            for mode in ('control','dual') if a.mode=='both' else (a.mode,):
                program(mode);fixture.probe(mode)
                for label,package,instrumented in [('normal',NORMAL,False),('detail',DETAIL,True)]:
                    collect(package,package.with_name(package.name.replace('.package.json','.symbols.json')),
                        NORMAL,OUT/('physical-'+mode+'-'+label+'.json'),trials=3,
                        instrumented=instrumented,reuse_immutable_assets=True)
        finally:restore_accepted()
