"""Physical original-engine replay; always restore the current demo selection."""
import argparse,hashlib,json,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from load_game import Loader,STATUS,BEGIN,READ,package_segments,require_hardware
from measure_pixel_lanes import timing_gate
from sm64_engine_slice import ROOT,OUT,LLVM,audit_isa

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def program(sof,name,label):
    timing_gate(sof.parent,name)
    with (OUT/(label+'-programming.log')).open('w') as log:
        subprocess.run(['C:/intelFPGA_lite/18.1/quartus/bin64/quartus_pgm.exe','-c','USB-Blaster [USB-0]','-m','JTAG','-o','p;'+str(sof)+'@1'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
def upload(loader,path):require_hardware(loader,json.loads(path.read_text()));loader.transfer(package_segments(path))
def symbols(stem):
    data=subprocess.check_output([str(LLVM/'llvm-nm.exe'),'--defined-only',str(ROOT/'build'/(stem+'.elf'))],text=True)
    return {line.split()[-1]:int(line.split()[0],16) for line in data.splitlines() if len(line.split())==3}
def read_words(loader,address,count):
    words=[]
    while len(words)<count:
        n=min(3,count-len(words));words+=list(loader.operation(READ,address+4*len(words),count=n)['words'][:n])
    return words
def frame_sample(loader):
    time.sleep(2);start=loader.operation(STATUS);begin=time.monotonic();time.sleep(1);end=loader.operation(STATUS);seconds=time.monotonic()-begin
    if start['held'] or end['held'] or end['scratch']>>16==0xdead:raise RuntimeError('Game failed: '+str(end))
    frames=(end['scratch']-start['scratch'])&0xffffffff
    if not 0<frames<10000:raise RuntimeError('No normal frame progress')
    return {'start':start,'end':end,'seconds':seconds,'frames':frames,'scope':'One short live frame-production sample; input is not forced neutral; not sustained FPS or a controlled movement/mission benchmark'}

def game_memory(loader):
    addresses=symbols('mario-original-engine-grounds-exec')
    loader.operation(BEGIN)
    bottom=addresses['_local_bss_end'];top=addresses['_stack_top']
    words=read_words(loader,bottom,(top-bottom)//4)
    first=next((i for i,x in enumerate(words) if x!=0xa55a3cc3),len(words))
    fields={name:read_words(loader,addresses[name],count) for name,count in [('game_player',8),('game_gpu_stats',13),('game_update_cycles',1),('game_cpu_cycles',1),('game_frame_cycles',1)]}
    return {'static_state_bytes':addresses['_data_end']-addresses['_data_start'],'static_bss_bytes':addresses['_bss_end']-addresses['_bss_start'],
            'observed_stack_high_water_bytes':top-bottom-4*first,'local_stack_region_bytes':top-bottom,'last_frame_fields':fields,
            'scope':'Observed stack low-water after startup and a short live frame sample; includes startup/renderer; no heap; not a worst-case full-level bound'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ip',default='192.168.7.2');p.add_argument('--diagnostic-only',action='store_true');p.add_argument('--game-only',action='store_true');a=p.parse_args()
    if a.diagnostic_only and a.game_only:raise ValueError('Choose only one reduced validation scope')
    baseline=json.loads((ROOT/'profiles/current-deployment.json').read_text());old_sof=ROOT/baseline['hardware']['file'];old_package=ROOT/baseline['package']
    candidate=json.loads((ROOT/'build/sdram-exec/fit-identity.json').read_text());new_sof=ROOT/candidate['file']
    if digest(old_sof)!=baseline['hardware']['sha256'] or digest(new_sof)!=candidate['sha256']:raise ValueError('Hardware image hash mismatch')
    native=json.loads((OUT/'native-trace.json').read_text())
    if len(native)!=96 or any(row['fault'] for row in native):raise ValueError('Native reference replay did not pass')
    diag=ROOT/'build/sm64-original-engine-diagnostic.package.json';game=ROOT/'build/mario-original-engine-grounds-exec.package.json'
    for package in (old_package,diag,game):package_segments(package)
    for stem in ('sm64-original-engine-diagnostic','mario-original-engine-grounds-exec'):audit_isa(ROOT/'build'/(stem+'.elf'))
    kept=OUT/'baseline';kept.mkdir(exist_ok=True)
    shutil.copy2(old_package,kept/old_package.name)
    for segment in json.loads(old_package.read_text())['segments']:shutil.copy2(old_package.parent/segment['file'],kept/segment['file'])
    restored_package=kept/old_package.name
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'baseline':baseline,'candidate':candidate,'scope':'Original grounds slice validation; diagnostic has 96 unpaced updates, no GPU work, and includes counter instrumentation; live rendering input is uncontrolled','diagnostic_only':a.diagnostic_only,'game_only':a.game_only,'restored':False}
    loader=Loader(ip=a.ip)
    changed=False
    try:
        record['baseline_frame_sample']=frame_sample(loader);save('physical-record.json',record)
        print('Programming existing SDRAM-execution image',flush=True);changed=True;program(new_sof,'SdramExecSoC','candidate')
        if not a.game_only:
            print('Loading original-engine diagnostic',flush=True);upload(loader,diag)
            deadline=time.monotonic()+60
            while True:
                status=loader.operation(STATUS)
                if status['scratch']==0xe061600d:break
                if status['scratch']>>16==0xdead:raise RuntimeError('Diagnostic fault: '+str(status))
                if time.monotonic()>deadline:raise TimeoutError('Original-engine replay did not finish within 60 seconds')
                time.sleep(.1)
            loader.operation(BEGIN)
            addresses=symbols('sm64-original-engine-diagnostic');report=read_words(loader,addresses['engine_report'],8)
            flat=read_words(loader,addresses['engine_trace'],96*12);trace=[flat[i:i+12] for i in range(0,len(flat),12)]
            record['diagnostic_report']=report;record['diagnostic_trace']=trace
            mismatch=[i for i,(actual,expected) in enumerate(zip(trace,native)) if actual[:5]!=expected['bits']+[expected['action'],expected['fault']]]
            record['native_mismatch_ticks']=mismatch;save('physical-record.json',record)
            if report[2] or report[3]!=96 or mismatch:raise RuntimeError('Original-engine replay differs from native reference: '+str(mismatch[:10]))
            if any(row[5]==0 or row[6]==0 for row in trace):raise RuntimeError('CPU snapshots did not capture update work')
            print('PASS: all 96 original-engine state/position records match native bit for bit',flush=True)
        if not a.diagnostic_only:
            print('Loading rendered original-engine grounds package',flush=True);upload(loader,game)
            record['engine_frame_sample']=frame_sample(loader);save('physical-record.json',record)
            record['game_memory']=game_memory(loader);save('physical-record.json',record)
            print('Original-engine frame progress:',record['engine_frame_sample']['frames'],flush=True)
    except Exception as error:
        record['error']=repr(error);raise
    finally:
        if changed:
            print('Restoring selected hardware and exact castle demo package',flush=True)
            try:
                program(old_sof,old_sof.stem,'restore');upload(loader,restored_package)
                record['restored_frame_sample']=frame_sample(loader);record['restored']=True
            except Exception as restore_error:
                record['restore_error']=repr(restore_error);save('physical-record.json',record);raise
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save('physical-record.json',record);loader.close()
if __name__=='__main__':main()
