import sys,json,ctypes as c,math
from pathlib import Path
sys.path.insert(0,'scripts')
import test_world_pipeline as t,world_assets
T=t.WorldTests; T.setUpClass(); lib=T.lib
areas=world_assets.compile_world(json.loads(Path('build/castle/world.json').read_text()))[-1]
report={'method':'native production player_floor, every compiled floor centroid; indexed versus exhaustive queries','areas':[]}
for a in areas:
    fs=(t.Floor*len(a['floors']))(*(t.Floor(*(t.Point(*p) for p in pts),*r) for pts,r in a['floors']))
    ws=(t.Wall*len(a['walls']))(*(t.Wall(*(t.Point(*p) for p in pts),*r) for pts,r in a['walls']))
    w=t.World(fs,ws,len(fs),len(ws),*a['spawn'],24,60,180,32,4,42,-16000)
    normals=((c.c_int16*3)*len(fs))(*((c.c_int16*3)(*n) for n in a['floor_normals']))
    fi=(c.c_uint16*len(a['floor_indices']))(*a['floor_indices']);wi=(c.c_uint16*len(a['wall_indices']))(*a['wall_indices'])
    missing=[];different=[];total=0
    for i,(pts,_) in enumerate(a['floors']):
        x=sum(p[0] for p in pts)//3; z=sum(p[2] for p in pts)//3
        n=a['floor_normals'][i]; ceiling=math.ceil(pts[0][1]-(n[0]*(x-pts[0][0])+n[2]*(z-pts[0][2]))/n[1])+2
        lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
        expected=lib.player_floor(c.byref(w),x,z,ceiling)
        if expected==-32768: missing.append({'source':a['floor_metadata'][i]['source'],'x':x,'z':z,'ceiling':ceiling})
        cx=(x-a['grid_origin'][0])//512;cz=(z-a['grid_origin'][1])//512
        sf,nf,sw,nw=a['grid'][cz*a['grid_size'][0]+cx]
        fp=c.cast(c.byref(fi,sf*2),c.POINTER(c.c_uint16));wp=c.cast(c.byref(wi,sw*2),c.POINTER(c.c_uint16))
        lib.player_bind_query(c.byref(w),fp,nf,wp,nw,16000,normals)
        actual=lib.player_floor(c.byref(w),x,z,ceiling)
        if actual!=expected: different.append({'source':a['floor_metadata'][i]['source'],'x':x,'z':z,'full':expected,'indexed':actual})
        total+=1
    report['areas'].append({'id':a['id'],'samples':total,'no_floor':missing,'grid_mismatches':different})
Path('build/terrain-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps([{'id':a['id'],'samples':a['samples'],'no_floor':len(a['no_floor']),'grid_mismatches':len(a['grid_mismatches'])} for a in report['areas']],indent=2))
