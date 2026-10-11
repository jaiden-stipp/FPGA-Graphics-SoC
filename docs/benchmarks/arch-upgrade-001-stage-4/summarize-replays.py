import sys,json,re
from pathlib import Path
sys.path.insert(0,'scripts')
from profile_cpu import GPU
out=Path('build/arch-stage4')
report={'scope':'Deterministic terrain/fixture streams; excludes actors and physical VGA capture','replays':{}}
for kind in ('castle','quake','fixtures'):
 p=out/(kind+'-comparison.json')
 if not p.exists():continue
 result=json.loads(p.read_text());row={'exact':result['exact'],'triangles':result['after_triangles'],'variants':{}}
 for mode,base in [('stage3',Path('build/arch-stage3')/(kind+'-overlap')),('dual',out/(kind+'-dual'))]:
  frames={}
  for line in (base/'capture/frame-timeline.log').read_text().splitlines():
   parts=line.split();f=int(parts[0]);frames.setdefault(f,{})
   if parts[1]=='begin':frames[f]['begin']=int(parts[2])
   elif parts[1]=='swap_request':frames[f]['swap_request']=int(parts[2])
   elif parts[1]=='swap_ack':
    stats=int(parts[3].split('=')[1],16)
    frames[f]['gpu']=dict(zip(GPU,[(stats>>(32*(12-i)))&0xffffffff for i in range(13)]))
  for v in frames.values():v['begin_to_swap_request']=v['swap_request']-v['begin']
  row['variants'][mode]=frames
 for f,a in row['variants']['stage3'].items():
  b=row['variants']['dual'][f]
  if any(a['gpu'][k]!=b['gpu'][k] for k in GPU[:7]):raise RuntimeError('Replay event mismatch')
 report['replays'][kind]=row
 print(kind,'exact',row['exact'],'events exact',True,'clear',[r['gpu']['clear_cycles'] for r in row['variants']['dual'].values()])
(out/'replay-measurements.json').write_text(json.dumps(report,indent=2)+'\n')
