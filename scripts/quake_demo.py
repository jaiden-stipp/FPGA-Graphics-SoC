"""Original Quake meshes/frames -> a scoped interactive, portable game module.

MDL6/BSP29 references: id-Software/Quake WinQuake/modelgen.h and bspfile.h.
No original Quake engine behavior is claimed. World source selection is unchanged.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import game_assets
import portable_game
import quake_assets as q

ROOT=Path(__file__).resolve().parents[1]

def mdl(data,palette,prefix):
    if len(data)<84:raise ValueError('Truncated MDL')
    h=struct.unpack_from('<ii3f3ff3f8if',data)
    if h[:2]!=(0x4f504449,6):raise ValueError('Expected MDL6')
    scale=h[2:5];origin=h[5:8];skins,width,height,nv,nt,nf=h[12:18]
    if not all(math.isfinite(v) for v in h[2:12]) or not (1<=skins<=32 and 1<=width<=1024 and 1<=height<=1024 and 3<=nv<=4096 and 1<=nt<=8192 and 1<=nf<=1024):
        raise ValueError('Invalid MDL limits')
    cursor=84;skin=None
    for _ in range(skins):
        if struct.unpack_from('<i',data,cursor)[0]!=0:raise ValueError('Grouped MDL skins unsupported')
        cursor+=4
        pixels=data[cursor:cursor+width*height]
        if len(pixels)!=width*height:raise ValueError('Truncated skin')
        if skin is None:skin=pixels
        cursor+=width*height
    st=q.records(data[cursor:cursor+nv*12],'<3i');cursor+=nv*12
    tris=q.records(data[cursor:cursor+nt*16],'<4i');cursor+=nt*16
    frames=[]
    for _ in range(nf):
        if struct.unpack_from('<i',data,cursor)[0]!=0:raise ValueError('Grouped MDL frames unsupported')
        cursor+=4
        name=data[cursor+8:cursor+24].split(b'\0')[0].decode('ascii');cursor+=24
        packed=q.records(data[cursor:cursor+nv*4],'<4B');cursor+=nv*4
        frames.append((name,[[origin[a]+p[a]*scale[a] for a in range(3)] for p in packed]))
    chosen=[f for f in frames if f[0].startswith(prefix)]
    if not chosen:raise ValueError('Animation frame prefix missing')
    chosen=chosen[:8] # Explicit bounded source clip selection, no interpolation.
    floor=min(v[2] for v in chosen[0][1])
    for _,points in chosen:
        for p in points:p[2]-=floor
    triangles=[]
    for face,a,b,c in tris:
        if min(a,b,c)<0 or max(a,b,c)>=nv:raise ValueError('MDL triangle index')
        uv=[(s+(width//2 if seam and not face else 0),t) for seam,s,t in [st[i] for i in (a,b,c)]]
        # Flat original skin centroid sample: declared appearance approximation.
        sx=max(0,min(width-1,round(sum(s for s,_ in uv)/3)))
        sy=max(0,min(height-1,round(sum(t for _,t in uv)/3)))
        index=skin[sy*width+sx]
        if index==0:index=min(range(1,256),key=lambda i:sum((palette[i][k]-palette[0][k])**2 for k in range(3)))
        triangles.append([a,b,c,index])
    return chosen,triangles,{'sha256':q.digest(data),'vertices':nv,'triangles':nt,
        'source_frames':nf,'frame_names':[f[0] for f in frames],'selected_frames':[f[0] for f in chosen],'local_floor_rebase':floor,
        'appearance':'original skin centroid palette sample per face; opaque flat colors'}

def brush(lumps,index,palette):
    models=q.records(lumps[14],'<9f7i');model=models[index]
    vertices=q.records(lumps[3],'<3f');faces=q.records(lumps[7],'<hhihh4Bi')
    edges=q.records(lumps[12],'<2H');surf=[v[0] for v in q.records(lumps[13],'<i')]
    center=[(model[a]+model[a+3])/2 for a in range(3)];center[2]=model[2]+1
    points=[];mapping={};triangles=[];omitted=0
    color=min(range(1,256),key=lambda i:sum((palette[i][k]-[144,88,40][k])**2 for k in range(3)))
    for face_id in range(model[-2],model[-2]+model[-1]):
        _,_,start,count,*_=faces[face_id]
        ids=[edges[abs(e)][0 if e>=0 else 1] for e in surf[start:start+count]]
        for n in range(1,len(ids)-1):
            tri=[ids[0],ids[n],ids[n+1]]
            if not any(portable_game.area([vertices[i] for i in tri])):omitted+=1;continue
            for i in tri:
                if i not in mapping:mapping[i]=len(points);points.append([vertices[i][a]-center[a] for a in range(3)])
            triangles.append([mapping[i] for i in tri]+[color])
    return points,triangles,{'source_model':index,'first_face':model[-2],'faces':model[-1],
        'source_origin':center,'zero_area_fans_omitted':omitted,
        'appearance':'explicit flat brown door color; texture mapping unsupported'}

def emit(pak,directory):
    directory.mkdir(parents=True,exist_ok=True)
    portable_game.export_quake(pak,ROOT/'profiles/quake-e1m1.json',directory/'scene.json')
    scene=json.loads((directory/'scene.json').read_text());entries=q.pak_entries(pak.read_bytes())
    palette=[tuple(p) for p in q.records(entries['gfx/palette.lmp'],'<3B')]
    soldier,enemy_tri,enemy_report=mdl(entries['progs/soldier.mdl'],palette,'run')
    armor,pickup_tri,pickup_report=mdl(entries['progs/armor.mdl'],palette,'')
    door_v,door_t,door_report=brush(q.bsp_lumps(entries['maps/e1m1.bsp']),1,palette)
    scene['target']['id']='de2-115-fixed-v2'
    scene['target']['required_features']+=['custom-rv32i-gameplay','mouse-look-v1','gpu-hud','dynamic-objects','mesh-frame-animation']
    scene['meshes'] += [{'id':'door','role':'actor','vertices':door_v,'triangles':door_t},
        {'id':'pickup','role':'actor','vertices':armor[0][1],'triangles':pickup_tri,'retain_degenerate_actor_faces':True},
        {'id':'enemy','role':'actor','vertices':soldier[0][1],'triangles':enemy_tri,'retain_degenerate_actor_faces':True}]
    scene['provenance']['interactive_demo']={'original_engine_ported':False,'door':door_report,
        'pickup':pickup_report,'enemy':enemy_report,
        'placement':'demo relocates source brush/models onto imported floors near the start',
        'rules':'E toggles rising door; armor once +50; enemy patrol/contact damage; F/left mouse hitscan 10 damage'}
    chunks,_,floors,_,report=portable_game.compile_scene(scene,False)
    handles={m['id']:m['handles'] for m in report['logical_meshes']}
    positions={}
    for name,x,z in [('door',0,1000),('pickup',0,600),('enemy',320,1440)]:
        floor=game_assets.floor_height(floors,x,z,512)
        if floor== -32768:raise ValueError('Demo object missing supporting floor')
        positions[name]=[x,floor,z]
    # Original spawn faces a real blocking wall. The scoped demo starts on the
    # walkable floor beyond it, without removing original level triangles.
    start_floor=game_assets.floor_height(floors,0,400,512)
    if start_floor==-32768:raise ValueError('Demo spawn missing floor')
    source_origin=scene['coordinates']['origin']
    scene['controller']['spawn']=[source_origin[0],source_origin[1]+100,source_origin[2]+start_floor/4]
    scene['provenance']['interactive_demo']['spawn_gpu']=[0,start_floor,400]
    scene['provenance']['interactive_demo']['spawn_policy']='walkable floor beyond original starting wall; world faces unchanged'
    lines=['// Generated source model bindings; immutable SDRAM data.','#ifndef QUAKE_DEMO_DATA_H','#define QUAKE_DEMO_DATA_H',
        '#include "game_services.h"','#define DEMO_STORAGE __attribute__((section(".game_assets")))']
    for name in ('door','pickup','enemy'):
        hs=handles[name]
        lines += [f'#define DEMO_{name.upper()}_FIRST {hs[0]}u',f'#define DEMO_{name.upper()}_COUNT {len(hs)}u']
        verts=[v for h in hs for v in chunks[h][0]]
        bounds=[c for axis in range(3) for c in (min(v[axis] for v in verts),max(v[axis] for v in verts))]
        lines.append(f'static const game_bounds_t demo_{name}_bounds={{'+','.join(map(str,bounds))+'};')
        lines.append(f'static const int16_t demo_{name}_position[3]={{'+','.join(map(str,positions[name]))+'};')
    rotations=[[round(math.cos(i*math.tau/256)*256),round(math.sin(i*math.tau/256)*256)] for i in range(256)]
    lines.append('static const DEMO_STORAGE int16_t demo_rotations[256][2]={'+','.join('{'+','.join(map(str,r))+'}' for r in rotations)+'};')
    # Recover each hardware vertex's original MDL source ID from IR mapping.
    enemy_maps=report['chunk_source_triangles']
    for h in handles['enemy']:
        mesh=chunks[h];ids=[None]*len(mesh[0])
        for tri,record in zip(mesh[1],enemy_maps[h]['triangles']):
            for packed,source in zip(tri[:3],record['source_vertices']):ids[packed]=source
        frame_data=[]
        for _,frame in soldier:
            frame_data.append([tuple(round(frame[i][a]*4) for a in (0,2,1)) for i in ids])
        lines.append(f'static const DEMO_STORAGE scene_vertex_t demo_enemy_frames_{h}[{len(soldier)}][{len(ids)}]={{'+
            ','.join('{'+','.join('{'+','.join(map(str,v))+'}' for v in f)+'}' for f in frame_data)+'};')
    lines += [f'#define DEMO_ENEMY_FRAMES {len(soldier)}u','static int demo_enemy_upload(uint32_t frame) {']
    for h in handles['enemy']:lines.append(f'if(game_mesh_frame({h},demo_enemy_frames_{h}[frame],{len(chunks[h][0])}))return -1;')
    lines += ['return 0;}']
    for name,rgb in [('WHITE',[255,255,255]),('BLACK',[0,0,0]),('RED',[224,32,32]),('GOLD',[240,192,32]),('GREEN',[32,192,32])]:
        index=min(range(1,256),key=lambda i:sum((palette[i][k]-rgb[k])**2 for k in range(3)))
        lines.append(f'#define DEMO_{name} {index}u')
    lines+=['#endif','']
    (ROOT/'firmware/generated/quake_demo_data.h').write_text('\n'.join(lines))
    (directory/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
    project={'format':'soc-game-project','version':1,'name':'quake-interactive','scene':'scene.json',
        'port':{'kind':'custom','sources':['../../firmware/ports/quake_demo.c','../../firmware/src/game_services.c'],
        'exports':['game_input_decode','game_movement_keys','game_view_update','game_object_overlap','game_door_step',
            'game_pickup_step','game_animation_frame','game_mesh_frame','game_hud_begin','game_hud_rect','game_hud_number']}}
    (directory/'game.project.json').write_text(json.dumps(project,indent=2)+'\n')
    (directory/'demo-report.json').write_text(json.dumps({'handles':handles,'positions':positions,
        'enemy':enemy_report,'pickup':pickup_report,'door':door_report,'triangles':report['source_triangles']},indent=2)+'\n')
    print(f'Quake interactive demo: {len(chunks)} handles, {report["source_triangles"]} triangles, {len(soldier)} original run frames; {directory}/game.project.json')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pak',type=Path,default=ROOT/'build/quake-shareware/pak0.pak')
    p.add_argument('--out',type=Path,default=ROOT/'build/quake-interactive');a=p.parse_args()
    try:emit(a.pak,a.out)
    except (ValueError,OSError,struct.error) as e:p.exit(1,'ERROR: '+str(e)+'\n')
if __name__=='__main__':main()
