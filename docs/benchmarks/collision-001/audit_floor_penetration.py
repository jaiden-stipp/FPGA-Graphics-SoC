import sys,json,ctypes as c
from pathlib import Path
sys.path.insert(0,'scripts')
import test_world_pipeline as t,world_assets
T=t.WorldTests;T.setUpClass();lib=T.lib
if len(sys.argv)>1:
 lib=c.CDLL(str(Path(sys.argv[1]).resolve()))
 lib.player_bind_query.argtypes=T.lib.player_bind_query.argtypes
 lib.player_floor.argtypes=T.lib.player_floor.argtypes
 lib.player_step.argtypes=T.lib.player_step.argtypes
areas=world_assets.compile_world(json.loads(Path('build/castle/world.json').read_text()))[-1]
report=[]
for a in areas:
 fs=(t.Floor*len(a['floors']))(*(t.Floor(*(t.Point(*p) for p in pts),*r) for pts,r in a['floors']))
 ws=(t.Wall*len(a['walls']))(*(t.Wall(*(t.Point(*p) for p in pts),*r) for pts,r in a['walls']))
 w=t.World(fs,ws,len(fs),len(ws),*a['spawn'],24,60,180,32,4,42,-16000)
 normals=((c.c_int16*3)*len(fs))(*((c.c_int16*3)(*n) for n in a['floor_normals']))
 faults=[];cases=0
 for f,(pts,_) in enumerate(a['floors']):
  x=sum(p[0] for p in pts)//3;z=sum(p[2] for p in pts)//3
  lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
  y=lib.player_floor(c.byref(w),x,z,16000)
  for keys in (1,2,4,8,5,6,9,10):
   p=t.Player(x,y,z,0,1,0,0,0)
   for tick in range(12):
    old=(p.x,p.y,p.z,p.grounded)
    lib.player_step(c.byref(p),c.byref(w),keys);cases+=1
    # Grounded motion must not enter a continuous supporting floor above its feet.
    if not old[3] or p.respawns:break
    # Independently identify surfaces covering both endpoints; use unbounded Python cross products.
    for i in (f,):
     v=a['floors'][i][0]
     def inside(x,z):
      e=[(v[(j+1)%3][0]-v[j][0])*(z-v[j][2])-(v[(j+1)%3][2]-v[j][2])*(x-v[j][0]) for j in range(3)]
      return min(e)>=0 or max(e)<=0
     if not inside(old[0],old[2]) or not inside(p.x,p.z):continue
     n=a['floor_normals'][i]
     def height(x,z):return v[0][1]-int((n[0]*(x-v[0][0])+n[2]*(z-v[0][2]))/n[1])
     oy=height(old[0],old[2]);ny=height(p.x,p.z)
     if abs(oy-old[1])<=1 and ny>p.y+1:
      faults.append({'floor':i,'start_floor':f,'keys':keys,'tick':tick,'before':old,'after':[p.x,p.y,p.z,p.grounded],'support_height':ny,'normal':n,'vertices':v});break
    if faults and faults[-1].get('start_floor')==f and faults[-1]['keys']==keys:break
 result={'area':a['id'],'ticks':cases,'penetrations':len(faults),'examples':faults[:10]};report.append(result);print(json.dumps(result),flush=True)
Path(sys.argv[2] if len(sys.argv)>2 else 'build/floor-penetration-candidate.json').write_text(json.dumps(report,indent=2)+'\n')


