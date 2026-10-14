"""Deploy the engine grounds build and smoke-test repeated jump/reset over UDP."""
import argparse,json,time
from datetime import datetime,timezone
from pathlib import Path
from load_game import Loader,STATUS,BEGIN,COMMIT,package_segments
from mouse_udp import Sender
from verify_sm64_engine_slice import ROOT,OUT,program,upload,frame_sample,symbols,read_words,digest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traversal',action='store_true',help='Longer water, shore, ledge-approach and advanced-control smoke tests')
    args=parser.parse_args();label='traversal' if args.traversal else 'movement-fix'
    identity=json.loads((ROOT/'build/sdram-exec/fit-identity.json').read_text())
    sof=ROOT/identity['file'];package=ROOT/'build/mario-original-engine-grounds-exec.package.json'
    if digest(sof)!=identity['sha256']:raise ValueError('Hardware image hash mismatch')
    package_segments(package)
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'hardware':identity,
            'package':json.loads(package.read_text()),'success':False,
            'scope':'Host-paced live UDP movement smoke tests, not cycle-exact replay or an FPS benchmark. Other senders are not disabled.'}
    def save():
        (OUT/(label+'-physical.json')).write_text(json.dumps(record,indent=2)+'\n')
    loader=Loader();sender=None
    try:
        program(sof,'SdramExecSoC',label)
        if args.traversal:
            upload(loader,ROOT/'build/sm64-original-engine-diagnostic.package.json')
            deadline=time.monotonic()+60
            while loader.operation(STATUS)['scratch']!=0xe061600d:
                if time.monotonic()>deadline:raise TimeoutError('Original-engine diagnostic did not complete')
                time.sleep(.1)
            loader.operation(BEGIN);diag=symbols('sm64-original-engine-diagnostic')
            flat=read_words(loader,diag['engine_trace'],96*12);trace=[flat[i:i+12] for i in range(0,len(flat),12)]
            reference=json.loads((OUT/'native-trace.json').read_text())
            mismatch=[i for i,(actual,expected) in enumerate(zip(trace,reference)) if actual[:5]!=expected['bits']+[expected['action'],expected['fault']]]
            record['diagnostic']={'report':read_words(loader,diag['engine_report'],8),'trace':trace,'native_mismatch_ticks':mismatch,
                                  'scope':'96 unpaced updates, no GPU work, counter intervals include snapshot instrumentation'}
            save()
            if len(reference)!=96 or mismatch or record['diagnostic']['report'][2] or record['diagnostic']['report'][3]!=96:
                raise RuntimeError('FPGA diagnostic differs from native reference')
            if any(not r[5] or not r[6] for r in trace):raise RuntimeError('Invalid CPU snapshot deltas')
            print('PASS all 96 diagnostic states match native floating-point bits and actions',flush=True)
        upload(loader,package);record['startup']=frame_sample(loader);save()
        addresses=symbols('mario-original-engine-grounds-exec')
        def fields():
            loader.operation(BEGIN)
            try:
                return {'fault':read_words(loader,addresses['castle_engine_fault'],1)[0],
                        'player':read_words(loader,addresses['game_player'],8),
                        'engine_state':read_words(loader,addresses['castle_engine_state'],4) if 'castle_engine_state' in addresses else [],
                        'frame':read_words(loader,addresses['game_frame'],1)[0]}
            finally:loader.operation(COMMIT)
        record['routes']=[]
        routes=[('backward-rollout',8,128,16),('diagonal-steep-jump-wall',5,128,16)]
        if args.traversal:routes=[('water-entry',4,128,20),('shore-exit',4,128,60),('ledge-approach',8,224,24),('advanced-controls',0,128,8)]
        for name,buttons,yaw,duration in routes:
            time.sleep(2);sender=Sender('192.168.7.2',4000);start=loader.operation(STATUS);begin=time.monotonic()
            for tick in range(duration*60):
                # Renderer yaw 128 maps to original engine yaw 0. The adapter
                # reflects stick X, so input 5 maps to engine input 6.
                keys=buttons|(16 if tick%90<14 else 0)
                if name=='advanced-controls':
                    phase=tick%240
                    keys=16 if phase<14 else 32 if phase<30 else 64 if 120<=phase<134 else 0
                sender.send(keys,yaw,0)
                time.sleep(max(0,begin+(tick+1)/60-time.monotonic()))
                if tick and tick%600==0:print('Progress:',name,tick//60,'seconds',flush=True)
            sender.close(yaw,0);sender=None;end=loader.operation(STATUS)
            state=fields();route={'name':name,'seconds':time.monotonic()-begin,'yaw':yaw,'buttons':buttons,'start':start,'end':end,'fields':state}
            record['routes'].append(route);save()
            if state['fault'] or end['scratch']>>16==0xdead or end['scratch']<=start['scratch']:
                raise RuntimeError('Movement smoke test failed: '+str(route))
            if name=='water-entry' and state['engine_state'][0]&0x1c0!=0xc0:raise RuntimeError('Water-entry route did not end swimming: '+str(route))
            if name=='shore-exit' and state['engine_state'][0]&0x1c0==0xc0:raise RuntimeError('Shore-exit route still swimming: '+str(route))
            print('PASS route:',name,'fault:',state['fault'],'frame progress:',end['scratch']-start['scratch'],flush=True)
        time.sleep(2);sender=Sender('192.168.7.2',4000)
        for _ in range(60):sender.send(128,128,0);time.sleep(1/60)
        sender.close(128,0);sender=None;time.sleep(1)
        record['reset']=fields();save()
        if record['reset']['fault'] or record['reset']['player'][7]!=1:
            raise RuntimeError('Held reset did not reset once: '+str(record['reset']))
        record['final']=frame_sample(loader);record['success']=True
        print('PASS reset once per press; game left running at spawn',flush=True)
    except Exception as error:
        record['error']=repr(error);raise
    finally:
        if sender:sender.close(128,0)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save();loader.close()

if __name__=='__main__':main()
