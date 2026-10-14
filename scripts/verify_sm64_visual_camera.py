"""Compare original visual/camera replay on FPGA and leave a verified game running.

Restores the archived 6fd250e package if validation fails. Live inputs are host
paced and other senders are not disabled; live frame samples are not FPS claims.
"""
import json,time
from datetime import datetime,timezone
from load_game import Loader,STATUS,BEGIN,COMMIT,package_segments
from mouse_udp import Sender
from verify_sm64_engine_slice import ROOT,OUT,upload,symbols,read_words,digest,frame_sample

def main():
    selection=json.loads((ROOT/'profiles/current-deployment.json').read_text())
    hardware=selection['hardware'];sof=ROOT/hardware['file']
    if digest(sof)!=hardware['sha256']:raise ValueError('Hardware image changed')
    baseline=ROOT/'docs/benchmarks/sm64-grounds-traversal-001/packages/mario-original-engine-grounds-exec.package.json'
    candidate=ROOT/'build/mario-original-engine-grounds-exec.package.json'
    diagnostic=ROOT/'build/sm64-original-visual-diagnostic.package.json'
    for p in (baseline,candidate,diagnostic):package_segments(p)
    expected=json.loads((OUT/'visual-native-trace.json').read_text())
    if len(expected)!=96 or any(r[0] for r in expected):raise ValueError('Native replay incomplete')
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'baseline_commit':'6fd250e','hardware':hardware,
            'candidate':json.loads(candidate.read_text()),'success':False,
            'scope':'96 unpaced original physics/camera/pose updates without GPU; direct cycle timers include timer-read overhead. Live tests are host-paced smoke tests; no sustained FPS or N64 equivalence claim.'}
    def save():(OUT/'visual-physical.json').write_text(json.dumps(record,indent=2)+'\n')
    loader=Loader();changed=False;sender=None
    try:
        changed=True;upload(loader,diagnostic)
        deadline=time.monotonic()+90
        while True:
            status=loader.operation(STATUS)
            if status['scratch']==0x5641600d:break
            if status['scratch']>>16==0xdead:raise RuntimeError('Visual diagnostic fault: '+str(status))
            if time.monotonic()>deadline:raise TimeoutError('Visual diagnostic did not finish')
            time.sleep(.1)
        loader.operation(BEGIN);addresses=symbols('sm64-original-visual-diagnostic')
        report=read_words(loader,addresses['visual_report'],8)
        flat=read_words(loader,addresses['visual_trace'],96*32);trace=[flat[i:i+32] for i in range(0,len(flat),32)]
        mismatch=[{'tick':i,'fields':[j for j,(a,b) in enumerate(zip(actual[3:],reference)) if a!=b]} for i,(actual,reference) in enumerate(zip(trace,expected)) if actual[3:]!=reference]
        record['diagnostic']={'report':report,'trace':trace,'mismatches':mismatch};save()
        if report[2] or report[3]!=96 or mismatch:raise RuntimeError('FPGA visual replay mismatch: '+str(mismatch[:8]))
        if any(any(not n for n in r[:3]) for r in trace):raise RuntimeError('Invalid cycle timers')
        print('PASS all 96 FPGA animation, pose, camera and movement records match native',flush=True)
        upload(loader,candidate);record['startup']=frame_sample(loader);save()
        addresses=symbols('mario-original-engine-grounds-exec')
        def fields():
            loader.operation(BEGIN)
            try:return {name:read_words(loader,addresses[name],count) for name,count in (
                ('castle_engine_fault',1),('castle_engine_state',4),('castle_engine_visual',4),
                ('castle_engine_view',6),('castle_engine_pose_cycles',1),('castle_engine_camera_cycles',1),
                ('game_player',8),('game_frame',1),('game_update_cycles',1),('game_frame_cycles',1))}
            finally:loader.operation(COMMIT)
        record['routes']=[]
        sender=Sender('192.168.7.2',4000)
        for name in ('walk-jump','rotate-camera','zoom-camera','punch-crouch'):
            start_state=fields();start=loader.operation(STATUS);begin=time.monotonic()
            for tick in range(360):
                buttons=4|(16 if tick%90<14 else 0) if name=='walk-jump' else 64 if name=='punch-crouch' and tick%120<15 else 32 if name=='punch-crouch' and tick%120>80 else 0
                yaw=(128+min(96,tick//2))&255 if name=='rotate-camera' else 224 if name in ('zoom-camera','punch-crouch') else 128
                pitch=20 if name=='zoom-camera' else 0
                sender.send(buttons,yaw,pitch)
                time.sleep(max(0,begin+(tick+1)/60-time.monotonic()))
            sender.send(0,yaw,pitch);time.sleep(.3)
            state=fields();end=loader.operation(STATUS)
            route={'name':name,'elapsed_seconds':time.monotonic()-begin,'start':start,'end':end,'start_fields':start_state,'fields':state}
            record['routes'].append(route);save()
            if state['castle_engine_fault'][0] or state['game_frame'][0]<=start_state['game_frame'][0] or end['scratch']>>16==0xdead:raise RuntimeError('Live route failed: '+str(route))
            print('PASS live route:',name,'frames:',state['game_frame'][0]-start_state['game_frame'][0],flush=True)
        for _ in range(60):sender.send(128,128,0);time.sleep(1/60)
        sender.close(128,0);sender=None;time.sleep(1)
        record['reset']=fields()
        if record['reset']['castle_engine_fault'][0] or record['reset']['game_player'][7]!=1:raise RuntimeError('Held reset failed')
        record['final']=frame_sample(loader);record['success']=True
        selection['package']=candidate.relative_to(ROOT).as_posix()
        (ROOT/'profiles/current-deployment.json').write_text(json.dumps(selection,indent=2)+'\n')
        print('PASS held reset; original camera/animation game left running at spawn',flush=True)
    finally:
        if sender:sender.close(128,0)
        if changed and not record['success']:
            upload(loader,baseline);selection['package']=baseline.relative_to(ROOT).as_posix()
            (ROOT/'profiles/current-deployment.json').write_text(json.dumps(selection,indent=2)+'\n')
            record['restored_baseline']=frame_sample(loader)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save();loader.close()

if __name__=='__main__':main()
