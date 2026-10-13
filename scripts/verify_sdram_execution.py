"""Timing-gated physical validation; restore accepted hardware/Mario on exit."""
import argparse,hashlib,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from load_game import Loader,STATUS,BEGIN,READ,package_segments,require_hardware
from measure_pixel_lanes import timing_gate
from soc import ROOT
OUT=ROOT/'build/sdram-exec'
BASE_PATH=OUT/'baseline.json'
if not BASE_PATH.exists():BASE_PATH=ROOT/'docs/benchmarks/sdram-exec-001/baseline.json'
BASE=json.loads(BASE_PATH.read_text(encoding='utf-8'))
OLD_SOF=ROOT/BASE['selection']['hardware']['file']
OLD_PACKAGE=OUT/'baseline'/Path(BASE['selection']['package']).name
NEW_SOF=ROOT/'build/quartus-sdram-exec/SdramExecSoC.sof'
NEW_PACKAGE=ROOT/'build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated-exec.package.json'
DIAG=ROOT/'build/sdram-exec-test.package.json'

def program(sof,label):
    name='SdramExecSoC' if sof==NEW_SOF else 'ArchStage5SoC'
    timing_gate(sof.parent,name)
    with (OUT/(label+'-programming.log')).open('w',encoding='utf-8') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],stdout=log,stderr=subprocess.STDOUT,check=True)

def load(loader,package,diagnostic=False):
    spec=json.loads(package.read_text(encoding='utf-8'));require_hardware(loader,spec)
    loader.transfer(package_segments(package))
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        status=loader.operation(STATUS)
        if status['scratch']>>16==0xdead:raise RuntimeError('Firmware failure: '+str(status))
        if diagnostic and status['scratch']==0x5eec600d:return status
        if not diagnostic and 0<status['scratch']<0x10000000 and not status['held']:return status
        time.sleep(.05)
    raise RuntimeError('Firmware did not start: '+str(status))

def samples(loader):
    time.sleep(2);rows=[]
    for _ in range(3):
        first=loader.operation(STATUS);start=time.monotonic();time.sleep(3)
        last=loader.operation(STATUS);elapsed=time.monotonic()-start
        if last['held'] or last['scratch']<=first['scratch'] or last['scratch']>>16==0xdead:raise RuntimeError('Game stopped')
        rows.append({'first_status':first,'last_status':last,'wall_seconds':elapsed,'displayed_frames':last['scratch']-first['scratch'],'fps':(last['scratch']-first['scratch'])/elapsed})
    return rows

def main():
    for p in (OLD_SOF,OLD_PACKAGE,NEW_SOF,NEW_PACKAGE,DIAG):
        if not p.exists():raise RuntimeError('Required local validation artifact missing: '+str(p)+'; preserve the accepted SOF and restore baseline firmware from the evidence archive')
    if hashlib.sha256(OLD_SOF.read_bytes()).hexdigest()!=BASE['selection']['hardware']['sha256']:raise RuntimeError('Accepted SOF changed')
    identity=json.loads((OUT/'fit-identity.json').read_text())
    if hashlib.sha256(NEW_SOF.read_bytes()).hexdigest()!=identity['sha256']:raise RuntimeError('Candidate SOF changed')
    for name,digest in json.loads((OUT/'fit-input-hashes.json').read_text()).items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Candidate source differs from fitted source: '+name)
    for p in (OLD_PACKAGE,NEW_PACKAGE,DIAG):package_segments(p)
    for p in (OUT/'final-simulation.log',OUT/'final-full-simulation.log',OUT/'udp-exec-loader.log'):
        t=p.read_text(encoding='utf-8')
        if 'PASS ' not in t or '** Fatal:' in t or '** Error:' in t:raise RuntimeError('Required verification failed: '+str(p))
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'baseline':BASE['selection'],'candidate':identity,
            'scope':'Three consecutive 3-second idle frame-progress samples per placement, one load each; not independent reset trials, a scripted movement route, or SM64 engine performance'}
    try:
        print('Loading accepted baseline for idle samples',flush=True)
        program(OLD_SOF,'baseline');loader=Loader()
        try:record['baseline_boot']=load(loader,OLD_PACKAGE);record['baseline_samples']=samples(loader)
        finally:loader.close()
        print('Programming timing-approved execution candidate',flush=True)
        program(NEW_SOF,'candidate');loader=Loader()
        try:
            status=loader.operation(STATUS,retries=40)
            if status['cpu_features']!=0x80000007 or status['gpu_features']!=3:raise RuntimeError('Candidate features mismatch')
            record['candidate_status']=status
            record['diagnostic_status']=load(loader,DIAG,True)
            # Holding CPU preserves memory results, while clearing peripheral state.
            loader.operation(BEGIN)
            symbols=json.loads((ROOT/'build/sdram-exec-test.symbols.json').read_text())
            values=[]
            for i in range(0,10,3):
                count=min(3,10-i);reply=loader.operation(READ,symbols['diagnostic_record']+4*i,count=count)
                values.extend(reply['words'][:count])
            if values[1]!=0x49430101 or values[5]!=0x80000007 or values[6]!=128 or values[7]!=0xabcd8123 or values[8]!=0x89abcdef or values[9]!=0x5eec600d:raise RuntimeError('Diagnostic record mismatch')
            record['diagnostic_record']=dict(zip(('execution_cycles','icache_abi','icache_hits','icache_misses','icache_fill_words','cpu_features','checksum','subword_result','local_initialized','success'),values))
            print('Loading same local-code game on new hardware',flush=True)
            record['candidate_local_boot']=load(loader,OLD_PACKAGE);record['candidate_local_samples']=samples(loader)
            print('Loading local boot + SDRAM-code game',flush=True)
            record['candidate_exec_boot']=load(loader,NEW_PACKAGE);record['candidate_exec_samples']=samples(loader)
            record['result']='success'
        finally:loader.close()
    except Exception as exc:
        record['result']='failed';record['error']=repr(exc);raise
    finally:
        print('Restoring accepted hardware and verified Mario package',flush=True)
        try:
            program(OLD_SOF,'restore');loader=Loader()
            try:
                first=load(loader,OLD_PACKAGE);time.sleep(1);last=loader.operation(STATUS)
                if last['held'] or last['scratch']<=first['scratch']:raise RuntimeError('Restored game did not advance')
                record['restored']={'first_status':first,'last_status':last,'sof_sha256':hashlib.sha256(OLD_SOF.read_bytes()).hexdigest()}
            finally:loader.close()
        except Exception as exc:
            record['restore_error']=repr(exc);raise
        finally:
            record['finished_utc']=datetime.now(timezone.utc).isoformat()
            (OUT/'physical-results.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--physical',action='store_true',required=True);p.parse_args();main()
