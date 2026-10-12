"""Software rendering comparison on the immutable accepted Stage 5 SOF."""
import sys,hashlib,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from load_game import Loader,STATUS,require_hardware,package_segments
from profile_cpu import collect
from measure_pixel_lanes import timing_gate
OUT=ROOT/'build/render-fixes'
BASE=OUT/'baseline/mario-castle-sdram-direct-packed-mul-geometry-uncapped.package.json'
NEW=ROOT/'build/mario-castle-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json'
FIT=ROOT/'build/quartus-arch-stage5-worker'
SOF=FIT/'ArchStage5SoC.sof'
SHA='e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14'
def restore(package):
    l=Loader()
    try:
        require_hardware(l,json.loads(package.read_text()));l.transfer(package_segments(package))
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            s=l.operation(STATUS)
            if s['scratch']>>16==0xdead:raise RuntimeError(str(s))
            if s['initialized'] and not s['held'] and 0<s['scratch']<0x10000000:break
            time.sleep(.05)
        else:raise RuntimeError('Game did not start')
        time.sleep(1);end=l.operation(STATUS)
        if end['held'] or end['scratch']<=s['scratch']:raise RuntimeError('No frame progress')
        return {'sof_sha256':SHA,'package':str(package),'segments':json.loads(package.read_text())['segments'],'first_status':s,'last_status':end}
    finally:l.close()
if __name__=='__main__':
    if '--deploy' in sys.argv:
        (OUT/'selected-running-check.json').write_text(json.dumps(restore(NEW),indent=2)+'\n');sys.exit()
    timing_gate(FIT,'ArchStage5SoC')
    if hashlib.sha256(SOF.read_bytes()).hexdigest()!=SHA:raise RuntimeError('Accepted SOF changed')
    for p in (BASE,NEW):package_segments(p)
    with (OUT/'programming.log').open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(SOF)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    l=Loader()
    try:
        s=l.operation(STATUS,retries=40)
        if s['cpu_features']!=0x80000003 or s['gpu_features']!=3:raise RuntimeError('Incorrect hardware capabilities')
        (OUT/'programmed-image.json').write_text(json.dumps({'sof':str(SOF),'sha256':SHA,'status':s},indent=2)+'\n')
    finally:l.close()
    try:
        for mode,p in [('baseline',BASE),('fixed',NEW)]:
            for moving in (False,True):
                print('Measuring',mode,'moving' if moving else 'standing',flush=True)
                collect(p,p.with_name(p.name.replace('.package.json','.symbols.json')),p,OUT/('physical-'+mode+('-moving' if moving else '-standing')+'.json'),trials=3,moving=moving,instrumented=False,reuse_immutable_assets=True)
    finally:
        (OUT/'rollback-running-check.json').write_text(json.dumps(restore(BASE),indent=2)+'\n')
