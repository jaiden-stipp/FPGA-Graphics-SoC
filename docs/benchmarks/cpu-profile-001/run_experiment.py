import sys,subprocess,hashlib,json,re,time
from pathlib import Path
sys.path.insert(0,'scripts')
from profile_cpu import collect
from load_game import Loader,STATUS,package_segments
ROOT=Path.cwd();out=ROOT/'build/cpu-profile'
old=ROOT/'build/quartus-line32/CacheLine32SoC.sof';new=ROOT/'build/quartus-cpu-profile/CpuProfileSoC.sof'
assert hashlib.sha256(old.read_bytes()).hexdigest()=='b9386eb9aad671dff8313ca61a22b6e04874dc22ab1e94f42c2732790576b4ce'
assert hashlib.sha256(new.read_bytes()).hexdigest()=='6744adf087bea5139d0170b69e4ca4c1461efe275036333c3f446e65b2c15888'
slacks=[float(v) for v in re.findall(r'Slack\s*:\s*([-+\d.]+)',(ROOT/'build/quartus-cpu-profile/CpuProfileSoC.sta.summary').read_text())];assert slacks and min(slacks)>=0
baseline=out/'baseline/mario-castle-sdram-direct.package.json';package_segments(baseline)
pgm='C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe'
def program(sof,label):
    with (out/(label+'-program.log')).open('w') as f:
        subprocess.run([pgm,'-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=f,stderr=subprocess.STDOUT,check=True)
report={'baseline_revision':'7280023','rtl_revision':'02d08ab','harness_revision':'b388364','baseline_sof_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'instrumented_sof_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'results':[]}
programmed=False
try:
    programmed=True;program(new,'instrumented')
    cases=[('instrumentation-control',baseline,out/'baseline/mario-castle-sdram-direct.symbols.json',False,False),
           ('profile-standing',ROOT/'build/mario-castle-profile.package.json',ROOT/'build/mario-castle-profile.symbols.json',False,True),
           ('batched-standing',ROOT/'build/mario-castle-profile-batched.package.json',ROOT/'build/mario-castle-profile-batched.symbols.json',False,True),
           ('profile-moving',ROOT/'build/mario-castle-profile.package.json',ROOT/'build/mario-castle-profile.symbols.json',True,True),
           ('batched-moving',ROOT/'build/mario-castle-profile-batched.package.json',ROOT/'build/mario-castle-profile-batched.symbols.json',True,True)]
    for label,pkg,syms,moving,instrumented in cases:
        print('BEGIN',label,flush=True)
        collect(pkg,syms,baseline,out/(label+'.json'),trials=3,moving=moving,instrumented=instrumented,reuse_immutable_assets=True)
        report['results'].append(label)
except Exception as exc:
    report['failure']=repr(exc);raise
finally:
    if programmed:
        print('Restoring original FPGA and original Mario',flush=True);program(old,'restore-original')
        l=Loader()
        try:
            l.transfer(package_segments(baseline));deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                status=l.operation(STATUS)
                if status['initialized'] and not status['held'] and 0<status['scratch']<0x10000000:break
                time.sleep(.05)
            else:raise RuntimeError('Original game restore failed')
            report['restored_status']=status
        finally:l.close()
    (out/'experiment.json').write_text(json.dumps(report,indent=2)+'\n')
