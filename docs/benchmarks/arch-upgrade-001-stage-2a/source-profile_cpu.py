"""Collect atomic completed-frame CPU/GPU profiles; restore baseline software."""
import argparse, json, time
from pathlib import Path
from load_game import Loader,BEGIN,READ,STATUS,package_segments,require_hardware
from keyboard_udp import packet
FIELDS=('cycles','retired','memory_freezes','dependency_bubbles','redirects','status_reads','full_status_reads')
PHASES=('tick','update','render','present')
EXTRA=('command_cycles','fifo_wait_span_cycles','bytes','commands','tick_wall_cycles','update_wall_cycles','cpu_wall_cycles','present_wall_cycles','frame_wall_cycles','frame','clock_hz','cpu_abi')
GPU=('triangles_submitted','triangles_clipped','triangles_culled','bounding_box_pixels','pixels_inside','depth_rejected','pixels_written','geometry_cycles','geometry_stall_cycles','raster_cycles','clear_cycles','total_cycles','swap_wait_cycles')
DETAIL=('chunk_selection','vertex_transform_outcodes','triangle_clipping','animation_step','animation_joints','animation_skin','camera')
FINE=('command_crc','command_checks','command_writes','clip_fraction','clip_intersection','gpu_admission','terrain_upload')
FINE_EVENTS=('gpu_admitted','gpu_draw_chunks','direct_draw_chunks','uploaded_chunks','clip_trivial_accept','clip_trivial_reject')
def window(loader,duration,moving,events,collect_samples=False):
    # The board uses the latest received UDP source port for replies. A single
    # socket avoids a concurrent controls sender redirecting loader responses.
    started=time.monotonic();next_sample=started;seq=0;samples=[]
    while time.monotonic()-started<duration:
        now=time.monotonic();elapsed=now-started
        mask=(4,1,8,2)[int(elapsed)%4] if moving else 0
        loader.socket.sendto(packet(seq,seq,mask),loader.target)
        events.append({'t':elapsed,'mask':mask,'sequence':seq&255});seq+=1
        if collect_samples and now>=next_sample:
            status=loader.operation(STATUS)
            if status['held'] or not status['initialized'] or not 0<status['scratch']<0x10000000:raise RuntimeError('Game failed: '+str(status))
            samples.append({'t':time.monotonic(),'frame':status['scratch']})
            next_sample=now+.25
        time.sleep(.02)
    loader.socket.sendto(packet(seq,seq,0),loader.target)
    return samples
def read_words(loader,address,count):
    values=[]
    for i in range(0,count,3): values.extend(loader.operation(READ,address+4*i,count=min(3,count-i))['words'][:min(3,count-i)])
    return values

def collect(package,symbols,restore,output,ip='192.168.7.2',port=4000,trials=3,moving=False,instrumented=True,reuse_immutable_assets=False):
    candidate=package_segments(package); baseline=package_segments(restore)
    if reuse_immutable_assets and [(a,d) for a,d,_ in candidate if a>=0x80000000] != [(a,d) for a,d,_ in baseline if a>=0x80000000]:raise ValueError('Reused assets must match baseline exactly')
    syms=json.loads(symbols.read_text())
    needed=['game_player','game_frame_cycles','game_cpu_cycles','game_update_cycles','game_present_cycles']
    if instrumented:needed+=['game_profile_slot','game_profile_slots']
    for name in needed:
        if name not in syms or syms[name]%4 or not 0<=syms[name]<65536:raise ValueError('Bad/missing symbol: '+name)
    if instrumented and syms['game_profile_slots']+2*53*4>65536:raise ValueError('Snapshot outside RAM')
    if instrumented and 'game_detail_slots' in syms and (syms['game_detail_slots']%4 or not 0<=syms['game_detail_slots']<=65536-2*16*4):raise ValueError('Detail snapshot outside RAM')
    if instrumented and 'game_fine_slots' in syms and (syms['game_fine_slots']%4 or not 0<=syms['game_fine_slots']<=65536-2*22*4):raise ValueError('Fine snapshot outside RAM')
    report={'package':str(package.resolve()),'segments':json.loads(package.read_text())['segments'],
            'scope':'Wall-clock controlled movement diagnostic; not a cycle-identical route' if moving else 'Standing spawn view',
            'instrumented':instrumented,'reuse_immutable_assets':reuse_immutable_assets,'trials':[],'restore':str(restore.resolve())}
    loader=Loader(ip,port)
    # A profiling run must enforce the same capability gate as normal loading.
    # Reject before BEGIN; do not replace a running game on incompatible hardware.
    try:require_hardware(loader,json.loads(package.read_text()))
    except Exception:
        loader.close();raise
    try:
        for trial in range(trials):
            loader.transfer(candidate if trial==0 or not reuse_immutable_assets else [segment for segment in candidate if segment[0]<65536])
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                initial=loader.operation(STATUS)
                if initial['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Startup failure: '+str(initial))
                if initial['initialized'] and not initial['held'] and 0<initial['scratch']<0x10000000:break
                time.sleep(.05)
            else:raise RuntimeError('Startup did not finish: '+str(initial))
            events=[]
            window(loader,3,False,events)
            events=[]
            samples=window(loader,5.3,moving,events,True)
            loader.operation(BEGIN)
            position=read_words(loader,syms['game_player'],3)
            position=[v if v<0x80000000 else v-0x100000000 for v in position]
            entry={'trial':trial+1,'samples':samples,'position':position,'input_packets':events,
                   'observed_fps':((samples[-1]['frame']-samples[0]['frame'])&0xffffffff)/(samples[-1]['t']-samples[0]['t'])}
            if instrumented:
                slot=read_words(loader,syms['game_profile_slot'],1)[0]
                if slot not in (0,1):raise RuntimeError('Invalid profile publication')
                values=read_words(loader,syms['game_profile_slots']+slot*53*4,53)
                entry['raw_words']=values
                entry['phases']={name:dict(zip(FIELDS,values[7*i:7*i+7])) for i,name in enumerate(PHASES)}
                entry['metrics']=dict(zip(EXTRA,values[28:40]));entry['gpu']=dict(zip(GPU,values[40:53]))
                if values[39]!=0x43500101 or values[38]!=50000000 or not values[37]:raise RuntimeError('Wrong profile ABI/clock/empty snapshot')
                if 'game_detail_slots' in syms:
                    detail=read_words(loader,syms['game_detail_slots']+slot*16*4,16)
                    if detail[14]!=values[37] or detail[15]!=0x44540101:raise RuntimeError('Mismatched detail frame/ABI')
                    entry['detail_raw_words']=detail
                    entry['detail']={name:{'cycles':detail[2*i],'calls':detail[2*i+1]} for i,name in enumerate(DETAIL)}
                if 'game_fine_slots' in syms:
                    fine=read_words(loader,syms['game_fine_slots']+slot*22*4,22)
                    if fine[20]!=values[37] or fine[21]!=0x464e0101:raise RuntimeError('Mismatched fine frame/ABI')
                    entry['fine_raw_words']=fine
                    entry['fine']={name:{'cycles':fine[2*i],'calls':fine[2*i+1]} for i,name in enumerate(FINE)}
                    entry['fine_events']=dict(zip(FINE_EVENTS,fine[14:20]))
                for phase in entry['phases'].values():
                    if phase['memory_freezes']+phase['dependency_bubbles']>phase['cycles'] or phase['retired']>phase['cycles']-phase['memory_freezes']:raise RuntimeError('Inconsistent CPU counters')
            else:entry['metrics']={name:read_words(loader,syms[name],1)[0] for name in needed if name!='game_player'}
            report['trials'].append(entry);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
            print('trial',trial+1,'fps',entry['observed_fps'],'position',position,'metrics',entry['metrics'],flush=True)
    except Exception as exc:
        report['failure']=repr(exc);raise
    finally:
        try:
            loader.transfer([segment for segment in baseline if segment[0]<65536] if reuse_immutable_assets and 'failure' not in report else baseline)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                status=loader.operation(STATUS)
                if status['initialized'] and not status['held'] and 0<status['scratch']<0x10000000:break
                time.sleep(.05)
            else:raise RuntimeError('Baseline game did not resume')
            report['restored_status']=status
        finally:loader.close();output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('--symbols',type=Path,required=True);p.add_argument('--restore',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ip',default='192.168.7.2');p.add_argument('--port',type=int,default=4000);p.add_argument('--trials',type=int,default=3);p.add_argument('--moving',action='store_true');p.add_argument('--uninstrumented',action='store_true');p.add_argument('--reuse-immutable-assets',action='store_true',help='Opt in only for games whose SDRAM asset segments stay immutable; verify full assets on first trial');a=p.parse_args()
    if not 1<=a.trials<=10:raise ValueError('trials must be 1..10')
    collect(a.package,a.symbols,a.restore,a.out,a.ip,a.port,a.trials,a.moving,not a.uninstrumented,a.reuse_immutable_assets)
