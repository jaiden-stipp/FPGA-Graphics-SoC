"""Compare complete CPU game streams and prepare canonical Stage 4 GPU replays."""
import argparse,json,hashlib
from pathlib import Path
from replay_render_route import write_input

def commands(path):
    rows=path.read_text().split()
    if not rows or any('x' in r.lower() or 'z' in r.lower() for r in rows):raise ValueError('Incomplete/unknown command stream')
    return [int(r,16) for r in rows]

def wire_command(word):
    op=word>>224;p=word&((1<<224)-1)
    def field(lo,bits):return (p>>lo)&((1<<bits)-1)
    def packed(lo,n):return field(lo,n*8).to_bytes(n,'big')
    if op==1:return 1,packed(0,4)
    if op==2:return 2,packed(0,19)
    if op==3:return 3,b''
    if op==4:return 4,packed(0,4)
    if op==5:return 5,packed(128,1)+packed(96,2)+packed(80,2)
    if op==6:return 6,packed(128,1)+packed(112,1)+packed(0,6)
    if op==7:return 7,packed(128,1)+packed(112,2)+packed(48,4)
    if op==8:return 8,packed(0,25)
    if op==9:return 11,packed(0,24)
    if op==10:return 12,packed(0,10)
    if op==11:return 13,packed(0,25)+packed(200,3)
    raise ValueError('Unknown internal command')

def compare(out):
    a=commands(out/'stream-0.commands.log');b=commands(out/'stream-1.commands.log')
    report={'scope':'Real CPUs/cache/SDRAM/shared game and actors, standing zero-input, three frames; synthetic decoder backpressure and immediate presentation acknowledgement. This is equivalence, not timing/FPS measurement.','commands_equal':a==b,'command_counts':[len(a),len(b)],'sha256':[hashlib.sha256((out/f'stream-{g}.commands.log').read_bytes()).hexdigest() for g in (0,1)],'frames':3,'exact':a==b}
    if a!=b:
        report['first_difference']=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
    for g,rows in enumerate((a,b)):
        packets=[wire_command(w) for w in rows]
        frame_ids=[int.from_bytes(p,'big') for op,p in packets if op==1]
        if frame_ids!=[1,2,3] or sum(op==3 for op,p in packets)!=3:raise ValueError('Incomplete game frames')
        write_input(packets,[{'frame':i,'label':f'complete-standing-frame-{i}'} for i in frame_ids],out/f'game-replay-{g}',{'scope':report['scope'],'cpu_stream_variant':g})
    (out/'game-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Exact complete-game command streams:',report['exact'])
    if not report['exact']:raise RuntimeError('Game command mismatch')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=Path('build/arch-stage5'));a=p.parse_args();compare(a.out)
