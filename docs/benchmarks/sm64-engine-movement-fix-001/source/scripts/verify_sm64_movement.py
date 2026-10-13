"""Deploy the engine grounds build and smoke-test repeated jump/reset over UDP."""
import json,time
from datetime import datetime,timezone
from pathlib import Path
from load_game import Loader,STATUS,BEGIN,COMMIT,package_segments
from mouse_udp import Sender
from verify_sm64_engine_slice import ROOT,OUT,program,upload,frame_sample,symbols,read_words,digest

def main():
    identity=json.loads((ROOT/'build/sdram-exec/fit-identity.json').read_text())
    sof=ROOT/identity['file'];package=ROOT/'build/mario-original-engine-grounds-exec.package.json'
    if digest(sof)!=identity['sha256']:raise ValueError('Hardware image hash mismatch')
    package_segments(package)
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'hardware':identity,
            'package':json.loads(package.read_text()),'success':False,
            'scope':'Host-paced live UDP movement smoke tests, not cycle-exact replay or an FPS benchmark. Other senders are not disabled.'}
    def save():
        (OUT/'movement-fix-physical.json').write_text(json.dumps(record,indent=2)+'\n')
    loader=Loader();sender=None
    try:
        program(sof,'SdramExecSoC','movement-fix')
        upload(loader,package);record['startup']=frame_sample(loader);save()
        addresses=symbols('mario-original-engine-grounds-exec')
        def fields():
            loader.operation(BEGIN)
            try:
                return {'fault':read_words(loader,addresses['castle_engine_fault'],1)[0],
                        'player':read_words(loader,addresses['game_player'],8),
                        'frame':read_words(loader,addresses['game_frame'],1)[0]}
            finally:loader.operation(COMMIT)
        record['routes']=[]
        for name,buttons in [('backward-rollout',8),('diagonal-steep-jump-wall',5)]:
            time.sleep(2);sender=Sender('192.168.7.2',4000);start=loader.operation(STATUS);begin=time.monotonic()
            for tick in range(960):
                # Renderer yaw 128 maps to original engine yaw 0. The adapter
                # reflects stick X, so input 5 maps to engine input 6.
                sender.send(buttons|(16 if tick%90<14 else 0),128,0)
                time.sleep(max(0,begin+(tick+1)/60-time.monotonic()))
            sender.close(128,0);sender=None;end=loader.operation(STATUS)
            state=fields();route={'name':name,'seconds':time.monotonic()-begin,'start':start,'end':end,'fields':state}
            record['routes'].append(route);save()
            if state['fault'] or end['scratch']>>16==0xdead or end['scratch']<=start['scratch']:
                raise RuntimeError('Movement smoke test failed: '+str(route))
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
