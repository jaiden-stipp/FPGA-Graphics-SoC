"""Matched software-only Stage 6 trials at 50 MHz; always restore Stage 5 Mario."""
import hashlib,json,shutil,subprocess,time
from pathlib import Path
from soc import ROOT
from load_game import Loader,STATUS,package_segments,require_hardware
from profile_cpu import collect
from measure_pixel_lanes import timing_gate

OUT=ROOT/'build/arch-stage6'
STEM='mario-castle-sdram-direct-packed-mul-geometry'
FIT=ROOT/'build/quartus-arch-stage5-worker'
SOF=FIT/'ArchStage5SoC.sof'
SOF_SHA='e2b1dce3d5814f348e0ca88b38fe49e494e68fddd9e897aeeac4c3a75b7c6e14'

def snapshot_baseline():
    out=OUT/'baseline';out.mkdir(parents=True,exist_ok=True)
    package=out/(STEM+'.package.json')
    if package.exists():
        package_segments(package) # Never overwrite the preserved baseline.
        return package
    for suffix in ('.package.json','.bin','.assets.bin','.symbols.json','.isa.json'):
        source=ROOT/'build'/(STEM+suffix)
        if source.exists():shutil.copyfile(source,out/source.name)
    spec=json.loads(package.read_text())
    if spec['segments'][0]['sha256']!='3b104f5a1a701732b866d7a31dea4091e937116e1f5730ac9d0c0c50863c5edf':raise RuntimeError('Not the accepted Stage 5 baseline')
    return package

def ready(loader):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        status=loader.operation(STATUS)
        if status['scratch']>>16==0xdead:raise RuntimeError('Startup failure '+str(status))
        if status['initialized'] and not status['held'] and 0<status['scratch']<0x10000000:return status
        time.sleep(.05)
    raise RuntimeError('Mario did not start')

def restore(package):
    loader=Loader()
    try:
        require_hardware(loader,json.loads(package.read_text()));loader.transfer(package_segments(package))
        first=ready(loader);time.sleep(1);last=loader.operation(STATUS)
        if last['held'] or last['scratch']<=first['scratch']:raise RuntimeError('Restored Mario did not progress')
        (OUT/'restored-running-check.json').write_text(json.dumps({'sof_sha256':SOF_SHA,'package':str(package),'segments':json.loads(package.read_text())['segments'],'first':first,'last':last},indent=2)+'\n')
    finally:loader.close()

def measure():
    OUT.mkdir(parents=True,exist_ok=True);baseline=snapshot_baseline()
    timing_gate(FIT,'ArchStage5SoC')
    if hashlib.sha256(SOF.read_bytes()).hexdigest()!=SOF_SHA:raise RuntimeError('SOF changed')
    with (OUT/'programming.log').open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(SOF)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)
    restore(baseline)
    try:
        for mode,package in [('tick-paced',ROOT/'build'/(STEM+'.package.json')),('uncapped',ROOT/'build'/(STEM+'-uncapped.package.json'))]:
            collect(package,package.with_name(package.name.replace('.package.json','.symbols.json')),baseline,
                OUT/('physical-'+mode+'.json'),trials=3,instrumented=False,reuse_immutable_assets=True)
    finally:restore(baseline)

if __name__=='__main__':measure()
