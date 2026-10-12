"""Stage 5 physical comparisons including configuration, transfer and polling."""
import argparse,json,hashlib,subprocess,time
from pathlib import Path
from soc import ROOT
from load_game import Loader,STATUS,BEGIN,package_segments,require_hardware
from profile_cpu import collect,read_words
from measure_pixel_lanes import timing_gate

OUT=ROOT/'build/arch-stage5'
NORMAL=ROOT/'build/mario-castle-sdram-direct-packed-mul.package.json'
DETAIL=ROOT/'build/mario-castle-sdram-direct-profile-detail-packed-mul.package.json'
WORKER=ROOT/'build/mario-castle-sdram-direct-packed-mul-geometry.package.json'
WORKER_DETAIL=ROOT/'build/mario-castle-sdram-direct-profile-detail-packed-mul-geometry.package.json'
ACCEPTED=ROOT/'build/quartus-arch-stage4-dual/ArchStage4SoC.sof'
ACCEPTED_SHA='52f7f8e3baf5d827a9dd18b3dc54f177aef666fce2ba361463830dfe8a0a8235'

def program(mode):
    name='ArchStage5SoC' if mode=='worker' else 'ArchStage5ControlSoC'
    fit=ROOT/('build/quartus-arch-stage5-'+mode);timing_gate(fit,name)
    sof=fit/(name+'.sof')
    with (OUT/(mode+'-programming.log')).open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        status=loader.operation(STATUS,retries=40)
        if status['gpu_features']!=3 or bool(status['cpu_features']&2)!=(mode=='worker'):raise RuntimeError('Wrong capabilities')
        (OUT/(mode+'-programmed-image.json')).write_text(json.dumps({'sof':str(sof),'sha256':hashlib.sha256(sof.read_bytes()).hexdigest(),'status':status},indent=2)+'\n')
    finally:loader.close()

def restore_accepted():
    if hashlib.sha256(ACCEPTED.read_bytes()).hexdigest()!=ACCEPTED_SHA:raise RuntimeError('Stage 4 SOF changed')
    with (OUT/'rollback-programming.log').open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(ACCEPTED)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    loader=Loader()
    try:
        spec=json.loads(NORMAL.read_text());require_hardware(loader,spec);loader.transfer(package_segments(NORMAL))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            first=loader.operation(STATUS)
            if first['initialized'] and not first['held'] and 0<first['scratch']<0x10000000:break
            time.sleep(.05)
        else:raise RuntimeError('Stage 4 Mario did not resume')
        time.sleep(1);last=loader.operation(STATUS)
        if last['held'] or last['scratch']<=first['scratch'] or last['cpu_features']&2:raise RuntimeError('Stage 4 restoration failed')
        (OUT/'final-running-check.json').write_text(json.dumps({'sof':str(ACCEPTED),'sof_sha256':ACCEPTED_SHA,'package':str(NORMAL),'segments':spec['segments'],'first_status':first,'last_status':last},indent=2)+'\n')
    finally:loader.close()

def probe():
    build=json.loads((OUT/'probe-build.json').read_text());report={'scope':'Same candidate CPU measures original production transform/outcodes versus actual MMIO adapter. Configuration, input writes, polling and result copies included. Static on-chip vertex data, not SDRAM game-time savings.','trials':[]}
    loader=Loader()
    try:
        require_hardware(loader,json.loads((OUT/'probe.package.json').read_text()))
        for i in range(3):
            loader.transfer(package_segments(OUT/'probe.package.json'));deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                status=loader.operation(STATUS)
                if status['scratch']>>16==0xdead:raise RuntimeError('Production oracle mismatch '+str(status))
                if status['scratch']==0x3500600d:break
                time.sleep(.02)
            else:raise RuntimeError('Probe timeout')
            loader.operation(BEGIN);raw=read_words(loader,build['symbols']['geometry_results'],40)
            cases=[{'software_cycles':raw[j*4],'adapter_cycles':raw[j*4+1],'worker_active_cycles':raw[j*4+2],'result_wait_cycles':raw[j*4+3]} for j in range(10)]
            report['trials'].append({'trial':i+1,'raw_words':raw,'cases':cases,'status':status})
            print('probe',i+1,[(r['software_cycles'],r['adapter_cycles']) for r in cases],flush=True)
    finally:loader.close();(OUT/'physical-worker-probe.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('worker','control','both'),default='both');p.add_argument('--probe-only',action='store_true');p.add_argument('--pending-equivalence',action='store_true',help='Experimental profiling only; promotion still requires exact game comparison');a=p.parse_args()
    if not a.probe_only and not a.pending_equivalence and not json.loads((OUT/'game-comparison.json').read_text())['exact']:raise RuntimeError('Game equivalence gate failed')
    (OUT/'measurement-gate.json').write_text(json.dumps({'equivalence_pending_during_profiling':a.pending_equivalence,'promotion_requires_equivalence':True},indent=2)+'\n')
    try:
        for mode in ('worker','control') if a.mode=='both' else (a.mode,):
            program(mode)
            if mode=='worker':probe()
            if a.probe_only:continue
            normal,detail=(WORKER,WORKER_DETAIL) if mode=='worker' else (NORMAL,DETAIL)
            for label,package,instrumented in [('normal',normal,False),('detail',detail,True)]:
                collect(package,package.with_name(package.name.replace('.package.json','.symbols.json')),NORMAL,
                    OUT/('physical-'+mode+'-'+label+'.json'),trials=3,instrumented=instrumented,reuse_immutable_assets=True)
    finally:restore_accepted()
