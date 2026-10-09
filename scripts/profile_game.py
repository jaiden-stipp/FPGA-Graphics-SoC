"""Measure a compatible software package on the existing FPGA; restore a baseline."""
import argparse
import json
from pathlib import Path
import time
import load_game

GPU_COUNTERS=('triangles_submitted','triangles_clipped','triangles_culled','bounding_box_pixels',
    'pixels_inside','depth_rejected','pixels_written','geometry_cycles','geometry_stall_cycles',
    'raster_cycles','clear_cycles','total_cycles','swap_wait_cycles')

def profile(package,restore,symbols,output,ip='192.168.7.2',port=4000,warmup=3,samples=8,interval=.25,names=()):
    # Hash, range and target validation precede any CPU reset/hold operation.
    trial=load_game.package_segments(package);baseline=load_game.package_segments(restore)
    addresses=json.loads(symbols.read_text())
    requested=list(names) or [n for n in ('game_frame','game_cpu_cycles','game_frame_cycles','game_present_cycles','game_update_cycles') if n in addresses]
    for name in requested:
        if name not in addresses or type(addresses[name]) is not int or not 0<=addresses[name]<=65532 or addresses[name]%4:
            raise ValueError('Missing/invalid CPU RAM symbol: '+name)
    stats=addresses.get('game_gpu_stats')
    if stats is not None and (type(stats) is not int or stats%4 or not 0<=stats<=65536-52):raise ValueError('Invalid GPU snapshot address')
    if not(0<=warmup<=60 and 2<=samples<=120 and .05<=interval<=5):raise ValueError('Invalid profiling interval')
    loader=load_game.Loader(ip,port)
    try:
        for path in (package,restore):load_game.require_hardware(loader,json.loads(path.read_text()))
        try:
            loader.transfer(trial);time.sleep(warmup)
            records=[]
            for i in range(samples):
                reply=loader.operation(load_game.STATUS)
                if reply['held'] or reply['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Game stopped or reported failure')
                records.append({'time':time.monotonic(),'frame':reply['scratch']})
                if i+1<samples:time.sleep(interval)
            loader.operation(load_game.BEGIN)
            metrics={n:loader.operation(load_game.READ,addresses[n],count=1)['words'][0] for n in requested}
            counters={n:loader.operation(load_game.READ,stats+4*i,count=1)['words'][0] for i,n in enumerate(GPU_COUNTERS)} if stats is not None else {}
            elapsed=records[-1]['time']-records[0]['time'];frames=(records[-1]['frame']-records[0]['frame'])&0xffffffff
            report={'package':str(package.resolve()),'samples':records,'observed_fps':frames/elapsed,
                'metrics':metrics,'gpu_stats':counters,'snapshot_cpu_held':True,
                'snapshot_note':'Last published frame counters; other globals may belong to a partial next frame.',
                'hardware_programming_requested':False,'restore_package':str(restore.resolve())}
        finally:
            print('Restoring baseline software package.',flush=True)
            loader.transfer(baseline)
        report['restored_status']=loader.operation(load_game.STATUS)
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        return report
    finally:loader.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package',type=Path);p.add_argument('--restore',type=Path,required=True)
    p.add_argument('--symbols',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--ip',default='192.168.7.2');p.add_argument('--port',type=int,default=4000)
    p.add_argument('--warmup',type=float,default=3);p.add_argument('--samples',type=int,default=8)
    p.add_argument('--interval',type=float,default=.25);p.add_argument('--symbol',action='append',default=[])
    a=p.parse_args();profile(a.package,a.restore,a.symbols,a.out,a.ip,a.port,a.warmup,a.samples,a.interval,a.symbol)

if __name__=='__main__':main()
