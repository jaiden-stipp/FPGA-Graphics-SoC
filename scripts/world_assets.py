"""Source-neutral, multi-area SDRAM world compiler. No source-game names here."""
import hashlib
import json
import math
import re
from pathlib import Path
import game_assets
import game_package
import portable_game

ROOT=Path(__file__).resolve().parents[1]

def vertex(p):
    if not isinstance(p,list) or len(p)!=3 or any(type(x) is not int or not -16000<=x<=16000 for x in p):
        raise ValueError('World positions require three signed, bounded integer source-space coordinates')
    return tuple(p)

def chunks(vertices,triangles,room_masks=None,tight=False,min_faces=0):
    """Partition by spatial centroid, retaining every supplied face and index order."""
    if type(min_faces) is not int or not 0<=min_faces<=256:raise ValueError('Minimum chunk faces must be 0..256')
    groups={}
    for i,t in enumerate(triangles):
        if len(t)!=4:raise ValueError('World triangles require three indices and a palette entry')
        for k in t[:3]:game_package.integer(k,0,len(vertices)-1)
        cell=tuple(sum(vertices[k][a] for k in t[:3])//1536 for a in (2,0))
        groups.setdefault(room_masks[i] if room_masks else 0,[]).append((cell,i,t))
    result=[]
    for mask,faces in groups.items():
        local={};points=[];packed=[];ids=[]
        def emit():
            if not packed:return
            low=[min(p[a] for p in points) for a in range(3)]
            high=[max(p[a] for p in points) for a in range(3)]
            center=[(a+b)//2 for a,b in zip(low,high)]
            result.append({'vertices':[[p[a]-center[a] for a in range(3)] for p in points],
                'triangles':packed[:],'source_triangles':ids[:],'origin':center,
                'bounds':[n for a in range(3) for n in (low[a],high[a])],'room_mask':mask})
        # Tight cell boundaries improve conservative resident admission.
        # Keep the legacy sorted face order, original winding and source IDs;
        # shared positions may be duplicated across chunks, never changed.
        previous_cell=None
        for cell,i,t in sorted(faces):
            keys=[tuple(vertices[k]) for k in t[:3]]
            if (tight and len(packed)>=min_faces and previous_cell is not None and cell!=previous_cell) or len(packed)>=256 or len(local)+len(set(keys)-local.keys())>128:
                emit();local={};points=[];packed=[];ids=[]
            previous_cell=cell
            for p in keys:
                if p not in local:local[p]=len(points);points.append(p)
            packed.append([*(local[p] for p in keys),t[3]]);ids.append(i)
        emit()
    return result

def compile_world(scene,tight_chunks=False,min_chunk_faces=0):
    if scene.get('format')!='soc-world-ir' or type(scene.get('version')) is not int or scene['version']!=1:raise ValueError('Expected soc-world-ir version 1')
    actors,palette,unused_floors,unused_walls,report=portable_game.compile_scene(scene['resident_scene'],False)
    if report['world_meshes'] or not 1<=len(actors)<=4:raise ValueError('World projects reserve one to four resident actor handles')
    areas=scene['areas']
    if not isinstance(areas,list) or not 1<=len(areas)<=32:raise ValueError('World requires 1..32 areas')
    ids=set();compiled=[];source_faces=0;collision_faces=0
    for area in areas:
        if not isinstance(area['id'],str) or not area['id'] or area['id'] in ids:raise ValueError('Area IDs must be unique and nonempty')
        ids.add(area['id']);points=[vertex(p) for p in area['vertices']]
        if not points or not isinstance(area['triangles'],list) or not area['triangles']:raise ValueError('Area needs geometry')
        for t in area['triangles']:
            if not isinstance(t,list) or len(t)!=4:raise ValueError('World triangles require three indices and a palette entry')
            game_package.integer(t[3],1,len(palette)-1)
        masks=area.get('triangle_room_masks')
        if masks is not None and (len(masks)!=len(area['triangles']) or any(type(m) is not int or not 0<=m<2**32 for m in masks)):raise ValueError('Invalid room mask table')
        packed=chunks(points,area['triangles'],masks,tight=tight_chunks,min_faces=min_chunk_faces);source_faces+=len(area['triangles'])
        if len(packed)>2048:raise ValueError('Area exceeds the software visibility index capacity of 2048 chunks')
        cp=[vertex(p) for p in area['collision']['vertices']];ct=area['collision']['triangles']
        if not cp or not ct or len(ct)>16384:raise ValueError('Area requires 1..16384 source collision faces')
        names=sorted({t[3] for t in ct if isinstance(t,list) and len(t)==5 and isinstance(t[3],str)})
        types=area['collision'].get('surface_types',{name:i+1 for i,name in enumerate(names)})
        if not isinstance(types,dict) or any(name not in types for name in names):raise ValueError('Surface type table must cover every collision tag')
        for name,value in types.items():
            if not isinstance(name,str) or not name:raise ValueError('Surface type names must be nonempty strings')
            game_package.integer(value,0,65535)
        forces=area['collision'].get('triangle_forces',[0]*len(ct))
        if not isinstance(forces,list) or len(forces)!=len(ct):raise ValueError('Collision force table must cover every face')
        for force in forces:game_package.integer(force,-32768,32767)
        collision_faces+=len(ct);floors=[];walls=[];surfaces=[];metadata=[];wall_metadata=[];degenerate=[];floor_normals=[]
        for i,t in enumerate(ct):
            if len(t)!=5 or not isinstance(t[3],str) or not t[3] or type(t[4]) is not int or not 0<=t[4]<=32:raise ValueError('Collision face needs indices, surface name, room 0..32')
            for k in t[:3]:game_package.integer(k,0,len(cp)-1)
            pts=[cp[k] for k in t[:3]];n=portable_game.area(pts);length=math.sqrt(sum(x*x for x in n))
            if not length:degenerate.append(i);continue
            normal=[round(x*4096/length) for x in n]
            bounds=[v for a in range(3) for v in (min(p[a] for p in pts),max(p[a] for p in pts))]
            wall=(pts,(*normal,*bounds,max(range(3),key=lambda a:abs(n[a]))))
            surfaces.append(wall)
            # Original outward floors; retain source surface names and room data.
            if n[1]>length*.01:
                slopes=[round(-n[a]*4096/n[1]) for a in (0,2)]
                # Runtime uses the source plane normal. Slopes only populate the
                # legacy record and are never used for this world's queries.
                slopes=[max(-32768,min(32767,s)) for s in slopes]
                floors.append((pts,(*bounds[:2],*bounds[4:],*slopes)))
                floor_normals.append(normal)
                metadata.append({'source':i,'surface':t[3],'type':types[t[3]],'force':forces[i],'room':t[4]})
            else:
                walls.append(wall)
                wall_metadata.append({'source':i,'surface':t[3],'type':types[t[3]],'force':forces[i],'room':t[4]})
        if not floors:raise ValueError('Area has no floors')
        physics=area.get('physics',{'speed':24,'radius':60,'height':180,'step_height':32,'gravity':4,'jump_speed':42,'kill_y':-16000})
        if not isinstance(physics,dict) or set(physics)!=set(portable_game.PHYSICS):raise ValueError('Unknown/missing world physics fields')
        for k in portable_game.PHYSICS:game_package.integer(physics[k],-16000,2048)
        if not(0<physics['speed']<=physics['radius']//2 and physics['radius']+physics['speed']<=128 and
               physics['height']>=2*physics['radius'] and 0<physics['gravity']<=16 and 0<physics['jump_speed']<=256 and
               physics['step_height']>=0 and physics['kill_y']<0):raise ValueError('World physics exceeds conservative spatial query bounds')
        vertex(area['spawn'])
        # Conservative footprint padding includes next-tick movement and capsule.
        grid=[];flat_f=[];flat_w=[]
        low=[min(p[a] for p in cp) for a in (0,2)];high=[max(p[a] for p in cp) for a in (0,2)]
        low=[x//512*512 for x in low];nx=(high[0]-low[0])//512+1;nz=(high[1]-low[1])//512+1
        for z in range(nz):
            for x in range(nx):
                minx=low[0]+x*512-128;maxx=minx+768;minz=low[1]+z*512-128;maxz=minz+768
                fi=[i for i,(_,r) in enumerate(floors) if r[0]<=maxx and r[1]>=minx and r[2]<=maxz and r[3]>=minz]
                wi=[i for i,(_,r) in enumerate(walls) if r[3]<=maxx and r[4]>=minx and r[7]<=maxz and r[8]>=minz]
                grid.append([len(flat_f),len(fi),len(flat_w),len(wi)]);flat_f+=fi;flat_w+=wi
        compiled.append({**area,'chunks':packed,'floors':floors,'walls':walls,'surfaces':surfaces,
            'floor_metadata':metadata,'wall_metadata':wall_metadata,'surface_types':types,'floor_normals':floor_normals,'degenerate_collision_sources':degenerate,'grid':grid,
            'floor_indices':flat_f,'wall_indices':flat_w,'grid_origin':low,'grid_size':[nx,nz]})
    report.update({'module':'world','areas':len(compiled),'stored_world_triangles':source_faces,
        'source_triangles':source_faces+report['actor_triangles'],
        'source_collision_triangles':collision_faces,'stored_world_chunks':sum(len(a['chunks']) for a in compiled),
        'collision_floors':sum(len(a['floors']) for a in compiled),'collision_walls':sum(len(a['walls']) for a in compiled),
        'area_reports':[{'id':a['id'],'source_triangles':len(a['triangles']),'chunks':len(a['chunks']),
            'floors':len(a['floors']),'walls':len(a['walls']),'grid_cells':len(a['grid']),
            'maximum_local_floor_candidates':max(c[1] for c in a['grid']),
            'maximum_local_wall_candidates':max(c[3] for c in a['grid']),
            'degenerate_collision_sources':a['degenerate_collision_sources']} for a in compiled]})
    return actors,palette,[],[],report,compiled

def header(areas):
    lines=['// Source-neutral SDRAM areas; generated, no source-game logic.',
        '#ifndef WORLD_DATA_H','#define WORLD_DATA_H','#include "world.h"',
        '#define WORLD_STORAGE __attribute__((section(".game_assets")))',
        f'#define WORLD_AREA_COUNT {len(areas)}u','extern const world_area_t world_areas[];',
        '#ifdef PORTABLE_DATA_DEFINE']
    def array(typ,name,rows,public=False):
        declaration=name if '[' in name else name+'[]'
        empty='0' if typ in ('uint8_t','uint16_t','int16_t') and '[' not in name else '{0}'
        lines.append(('' if public else 'static ')+'const WORLD_STORAGE '+typ+' '+declaration+'={'+','.join(rows or [empty])+'};')
    def row(values):return '{'+','.join(map(str,values))+'}'
    def collision_rows(data):return ['{'+','.join(row(p) for p in pts)+','+','.join(map(str,r))+'}' for pts,r in data]
    for i,a in enumerate(areas):
        for j,ch in enumerate(a['chunks']):
            array('scene_vertex_t',f'world_{i}_v{j}',[row(p) for p in ch['vertices']])
            array('scene_triangle_t',f'world_{i}_t{j}',[row(t) for t in ch['triangles']])
        array('world_chunk_t',f'world_{i}_chunks',[
            '{{world_%d_v%d,world_%d_t%d,%d,%d},%s,%s,%du}'%(i,j,i,j,len(ch['vertices']),len(ch['triangles']),row(ch['origin']),row(ch['bounds']),ch['room_mask']) for j,ch in enumerate(a['chunks'])])
        for typ,suffix,rows in [('collision_floor_t','floors',collision_rows(a['floors'])),
            ('collision_wall_t','walls',collision_rows(a['walls'])),('collision_wall_t','camera',collision_rows(a['surfaces'])),
            ('world_cell_t','cells',[row(c) for c in a['grid']]),
            ('uint16_t','fi',[str(x) for x in a['floor_indices']]),('uint16_t','wi',[str(x) for x in a['wall_indices']])]:array(typ,f'world_{i}_{suffix}',rows)
        array('int16_t',f'world_{i}_normals[][3]',[row(n) for n in a['floor_normals']])
        array('uint8_t',f'world_{i}_rooms',[str(m['room']) for m in a['floor_metadata']])
        for suffix,key in [('fs','floor_metadata'),('ws','wall_metadata')]:
            array('world_surface_t',f'world_{i}_{suffix}',[row([m['type'],m['source'],m['force'],m['room'],0]) for m in a[key]])
        physics=a.get('physics',{'speed':24,'radius':60,'height':180,'step_height':32,'gravity':4,'jump_speed':42,'kill_y':-16000})
        spawn=a['spawn'];floor=game_assets.floor_height(a['floors'],spawn[0],spawn[2],spawn[1]+256)
        if floor==-32768:raise ValueError('Area spawn has no original floor')
        a['validated_spawn']=[spawn[0],floor,spawn[2]]
        array('player_world_t',f'world_{i}_physics',['{world_%d_floors,world_%d_walls,%d,%d,%s}'%(i,i,len(a['floors']),len(a['walls']),','.join(map(str,[*a['validated_spawn'],*[physics[k] for k in portable_game.PHYSICS]])))])
    array('world_area_t','world_areas',[
        '{world_%d_chunks,%d,world_%d_physics,world_%d_camera,%d,world_%d_cells,world_%d_fi,world_%d_wi,%s,%s,world_%d_normals,world_%d_rooms,world_%d_fs,world_%d_ws}'%(i,len(a['chunks']),i,i,len(a['surfaces']),i,i,i,','.join(map(str,a['grid_origin'])),','.join(map(str,a['grid_size'])),i,i,i,i) for i,a in enumerate(areas)],True)
    lines+=['#endif','#endif',''];return '\n'.join(lines)

def generate(path,tight_chunks=False,min_chunk_faces=0):
    path=path.resolve();spec=json.loads(path.read_text());scene_path=(path.parent/spec['scene']).resolve();scene=json.loads(scene_path.read_text())
    if spec.get('format')!='soc-game-project' or type(spec.get('version')) is not int or spec['version']!=1:raise ValueError('Expected soc-game-project version 1')
    if not isinstance(spec.get('name'),str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',spec['name']):raise ValueError('Invalid world project name')
    if 'custom-rv32i-gameplay' not in scene['resident_scene']['target']['required_features']:raise ValueError('World port must declare custom-rv32i-gameplay')
    actors,palette,floors,walls,report,areas=compile_world(scene,tight_chunks=tight_chunks,min_chunk_faces=min_chunk_faces)
    report['terrain_packing']=f'centroid-cell-boundaries-min-{min_chunk_faces}-faces' if tight_chunks else 'legacy-capacity'
    # The existing project parser and shared resident compiler still validate ports.
    port=spec['port'];sources=[(path.parent/p).resolve() for p in port['sources']]
    if port['kind']!='custom' or not sources or any(not p.is_file() or p.suffix!='.c' or not p.is_relative_to(ROOT) for p in sources):raise ValueError('World requires an explicit custom gameplay port')
    api=port.get('exports',[])
    if not isinstance(api,list) or any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',n) for n in api):raise ValueError('Port exports must be C identifiers')
    report['source_scene_sha256']=hashlib.sha256(scene_path.read_bytes()).hexdigest()
    report['project_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['game_port']={'kind':'custom','sources':[{'file':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]}
    content=game_package.content(path,report,actors)
    content['configuration']['game']={'port':'custom','implementation_status':scene.get('implementation_status','world-services-demo')}
    content['configuration']['world']={'abi':'sdram-areas-v1','areas':len(areas),'stored_chunks':report['stored_world_chunks'],'render_scale':4,
        'near_gpu':257,'far_gpu':30000,'focal_gpu':256,'resident_handles':len(actors),
        'cache_policy':'uploads-between-frames; uncached-visible-triangles-software-clipped'}
    (ROOT/'firmware/generated/world_data.h').write_text(header(areas))
    resident=portable_game.header(actors,palette,[],[],{**report,'collision_floors':0,'collision_walls':0})
    (ROOT/'firmware/generated/portable_data.h').write_text(resident.replace('#ifdef PORTABLE_DATA_DEFINE','#include "world_data.h"\n#ifdef PORTABLE_DATA_DEFINE',1))
    (ROOT/f'build/{spec["name"]}.conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    return spec,content,scene['resident_scene']['target'],sources,api,report
