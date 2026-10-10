import sys,json,ctypes as c,time
from pathlib import Path
sys.path.insert(0,'scripts')
import test_world_pipeline as t,world_assets
T=t.WorldTests;T.setUpClass();lib=T.lib
areas=world_assets.compile_world(json.loads(Path('build/castle/world.json').read_text()))[-1]
report={'method':'Production player_step: indexed padded cell candidates versus all surfaces, identical plane normals; 8 headings, 12 ticks from each floor centroid','areas':[]}
for a in areas:
 fs=(t.Floor*len(a['floors']))(*(t.Floor(*(t.Point(*p) for p in pts),*r) for pts,r in a['floors']))
 ws=(t.Wall*len(a['walls']))(*(t.Wall(*(t.Point(*p) for p in pts),*r) for pts,r in a['walls']))
 w=t.World(fs,ws,len(fs),len(ws),*a['spawn'],24,60,180,32,4,42,-16000)
 normals=((c.c_int16*3)*len(fs))(*((c.c_int16*3)(*n) for n in a['floor_normals']))
 fi=(c.c_uint16*len(a['floor_indices']))(*a['floor_indices']);wi=(c.c_uint16*len(a['wall_indices']))(*a['wall_indices'])
 def bind(p,indexed):
  cx=(p.x-a['grid_origin'][0])//512;cz=(p.z-a['grid_origin'][1])//512
  if indexed and 0<=cx<a['grid_size'][0] and 0<=cz<a['grid_size'][1]:
   sf,nf,sw,nw=a['grid'][cz*a['grid_size'][0]+cx]
   fp=c.cast(c.byref(fi,sf*2),c.POINTER(c.c_uint16));wp=c.cast(c.byref(wi,sw*2),c.POINTER(c.c_uint16))
   lib.player_bind_query(c.byref(w),fp,nf,wp,nw,16000,normals)
  else:lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
 ticks=0;crossings=0;mismatches=[]
 for f,(pts,_) in enumerate(a['floors']):
  x=sum(p[0] for p in pts)//3;z=sum(p[2] for p in pts)//3
  n=a['floor_normals'][f];y=pts[0][1]-int((n[0]*(x-pts[0][0])+n[2]*(z-pts[0][2]))/n[1])
  for keys in (1,2,4,8,5,6,9,10):
   full=t.Player(x,y,z,0,1,0,0,0);grid=t.Player.from_buffer_copy(full)
   for tick in range(12):
    before=(grid.x//512,grid.z//512);bind(full,False);lib.player_step(c.byref(full),c.byref(w),keys)
    bind(grid,True);lib.player_step(c.byref(grid),c.byref(w),keys);ticks+=1
    if before!=(grid.x//512,grid.z//512):crossings+=1
    if bytes(full)!=bytes(grid):
     if len(mismatches)<10:mismatches.append({'floor':f,'keys':keys,'tick':tick,'full':[getattr(full,k) for k,_ in t.Player._fields_],'grid':[getattr(grid,k) for k,_ in t.Player._fields_]})
     break
 result={'id':a['id'],'ticks':ticks,'cell_crossings':crossings,'first_mismatches':mismatches};report['areas'].append(result);print(json.dumps(result),flush=True)
Path('build/terrain-movement-audit.json').write_text(json.dumps(report,indent=2)+'\n')
