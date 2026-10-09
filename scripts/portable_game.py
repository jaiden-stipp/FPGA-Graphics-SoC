"""Source-neutral scene compiler and project builder for the existing SoC ABI."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import game_assets
import game_package
import target_capabilities

ROOT = Path(__file__).resolve().parents[1]
PHYSICS = ('speed','radius','height','step_height','gravity','jump_speed','kill_y')

def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Scene coordinates must be finite numbers')
    return value

def triple(values):
    if not isinstance(values,list) or len(values)!=3:
        raise ValueError('Expected three coordinates')
    return [number(v) for v in values]

def area(points):
    a,b,c=points;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    return (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])

def compile_scene(scene, explorer=True):
    if not isinstance(scene,dict) or scene.get('format')!='soc-scene-ir' or type(scene.get('version')) is not int or scene['version']!=1:
        raise ValueError('Expected soc-scene-ir version 1')
    caps=target_capabilities.validate(scene['target']);limits=caps['limits']
    needed={'indexed-flat-rgb'}|({'triangle-collision','first-person-controller'} if explorer else set())
    if needed-set(scene['target']['required_features']):raise ValueError('Declare all features required by the selected runtime port')
    palette=scene['palette']
    if not isinstance(palette,list) or not 2<=len(palette)<=limits['palette_colors']:
        raise ValueError('Palette requires background plus 1..255 flat colors')
    for rgb in palette:
        if not isinstance(rgb,list) or len(rgb)!=3:raise ValueError('Expected RGB palette entries')
        for channel in rgb:game_package.integer(channel,0,255)
    transform=scene['coordinates'];origin=triple(transform['origin']);scale=number(transform['scale'])
    axes=transform['axes']
    if scale<=0 or not isinstance(axes,list) or len(axes)!=3 or any(type(a) is not int for a in axes) or sorted(abs(a) for a in axes)!=[1,2,3]:
        raise ValueError('Coordinates require a positive uniform scale and a signed axis permutation')
    signs=[1 if a>0 else -1 for a in axes];order=[abs(a)-1 for a in axes]
    inversions=sum(order[i]>order[j] for i in range(3) for j in range(i+1,3))
    reflected=math.prod(signs)*(-1 if inversions%2 else 1)<0
    maximum_error=0
    def position(point,actor=False):
        nonlocal maximum_error
        point=triple(point)
        raw=[signs[i]*(point[order[i]]-(0 if actor else origin[order[i]]))*scale for i in range(3)]
        if not all(math.isfinite(v) for v in raw):raise ValueError('Coordinate conversion overflow')
        rounded=tuple(round(v) for v in raw)
        if any(abs(v)>limits['coordinate_abs'] for v in rounded):
            raise ValueError('Geometry exceeds target coordinate range; explicitly select/rebase a smaller region')
        maximum_error=max(maximum_error,max(abs(a-b) for a,b in zip(raw,rounded)))
        return rounded
    meshes=scene['meshes']
    if not isinstance(meshes,list) or not meshes:raise ValueError('No source meshes')
    names=set();groups={'world':[],'actor':[]};source_count=0;retained_degenerate=0
    # World handles precede actors. Each logical source mesh may span handles.
    for mesh in meshes:
        name=mesh['id'];role=mesh.get('role','world')
        if not isinstance(name,str) or not name or name in names or role not in groups:
            raise ValueError('Mesh IDs must be unique; role must be world or actor')
        names.add(name)
        keep_degenerate=mesh.get('retain_degenerate_actor_faces',False)
        if type(keep_degenerate) is not bool or (keep_degenerate and role!='actor'):
            raise ValueError('Only actor meshes may explicitly retain zero-area animation/seam faces')
        original=mesh['vertices'];triangles=mesh['triangles']
        if not isinstance(original,list) or not isinstance(triangles,list) or not triangles:
            raise ValueError('Each source mesh needs vertices and triangles')
        original=[triple(p) for p in original]
        points={};packed=[];indices=[];local={};mapping=[]
        def flush():
            nonlocal packed,indices,local,mapping
            if indices:groups[role].append((packed,indices,{'mesh':name,'triangles':mapping}))
            packed=[];indices=[];local={};mapping=[]
        for ti,triangle in enumerate(triangles):
            if not isinstance(triangle,list) or len(triangle)!=4:raise ValueError('Triangulate faces; triangle must be [a,b,c,palette]')
            for index in triangle[:3]:game_package.integer(index,0,len(original)-1)
            game_package.integer(triangle[3],1,len(palette)-1)
            ids=list(triangle[:3]);source_count+=1
            source_degenerate=not any(area([original[i] for i in ids]))
            if source_degenerate and not keep_degenerate:raise ValueError('Degenerate source triangle; no faces are silently dropped')
            for i in ids:
                if i not in points:points[i]=position(original[i],role=='actor')
            quantized_degenerate=not any(area([points[i] for i in ids]))
            if quantized_degenerate and not keep_degenerate:raise ValueError('Triangle collapses after quantization; adjust explicit scale')
            if source_degenerate or quantized_degenerate:retained_degenerate+=1
            if reflected:ids[1],ids[2]=ids[2],ids[1]
            if len(indices)==limits['triangles_per_mesh'] or len(local)+len(set(ids)-local.keys())>limits['vertices_per_mesh']:flush()
            for i in ids:
                if i not in local:local[i]=len(packed);packed.append(points[i])
            indices.append(tuple(local[i] for i in ids)+(triangle[3],))
            mapping.append({'source_triangle':ti,'source_vertices':ids})
        flush()
    world=groups['world'];actors=groups['actor'];all_chunks=world+actors
    if len(all_chunks)>limits['mesh_handles']:
        raise ValueError(f'Scene requires {len(all_chunks)} resident mesh handles; target has {limits["mesh_handles"]}. Streaming is not implemented')
    if explorer and (not world or actors):raise ValueError('Default explorer requires static world meshes; actor/gameplay scenes need a custom port')
    settings=scene.get('controller')
    if explorer and settings is None:raise ValueError('Default explorer requires controller configuration')
    physics=settings['physics'] if settings else {}
    camera=settings['camera'] if settings else scene['projection']
    if settings:
        if set(physics)!=set(PHYSICS):raise ValueError('Unknown/missing controller physics fields')
        for key in PHYSICS:game_package.integer(physics[key],-8192,2048)
        if not (0<physics['speed']<=physics['radius']//2 and physics['height']>=32 and
                0<physics['gravity']<=16 and 0<physics['jump_speed']<=256 and physics['step_height']>=0 and physics['kill_y']<0):
            raise ValueError('Invalid bounded controller configuration')
    game_package.integer(camera['focal'],128,512);game_package.integer(camera['near_z'],limits['near_min'],1024)
    if settings:
        game_package.integer(camera['eye_height'],1,physics['height'])
        game_package.integer(camera['initial_yaw'],0,63);game_package.integer(camera['region_radius'],1,limits['coordinate_abs'])
    spawn=position(settings['spawn']) if settings else (0,0,0)
    floors,walls=game_assets.collision([(v,t) for v,t,_ in world]) if world else ([],[])
    if explorer and game_assets.floor_height(floors,spawn[0],spawn[2],spawn[1]+physics['step_height'])!=spawn[1]:
        raise ValueError('Explorer spawn must rest on imported collision geometry')
    logical=[]
    for h,(_,_,mapping) in enumerate(all_chunks):
        if logical and logical[-1]['id']==mapping['mesh']:logical[-1]['handles'].append(h)
        else:logical.append({'id':mapping['mesh'],'handles':[h]})
    report={'module':'portable','palette_colors':len(palette),'meshes':len(all_chunks),
        'world_meshes':len(world),'actor_meshes':len(actors),'world_triangles':sum(len(t) for _,t,_ in world),
        'actor_triangles':sum(len(t) for _,t,_ in actors),'source_triangles':source_count,
        'collision_floors':len(floors),'collision_walls':len(walls),'spawn_q8_8':list(spawn),
        'physics':physics,'camera':camera,'controller_present':settings is not None,
        'coordinates':transform,'winding_reflected':reflected,
        'maximum_quantization_error_gpu_units':maximum_error,'logical_meshes':logical,
        'explicitly_retained_degenerate_actor_faces':retained_degenerate,
        'chunk_source_triangles':[m for _,_,m in all_chunks],
        'policy':'No simplification, face dropping, color merging or unsupported-feature fallback',
        'source_provenance':scene.get('provenance',{})}
    return [(v,t) for v,t,_ in all_chunks],[tuple(c) for c in palette],floors,walls,report

def header(chunks,palette,floors,walls,report):
    lines=['// Shared scene IR -> unchanged GPU/collision ABI.','#ifndef PORTABLE_DATA_H','#define PORTABLE_DATA_H',
        '#include "game_runtime.h"','#include "first_person.h"',
        '#define PORTABLE_STORAGE __attribute__((section(".game_assets")))',
        f'#define PORTABLE_WORLD_MESHES {report["world_meshes"]}u',
        f'#define PORTABLE_MESH_COUNT {len(chunks)}u',f'#define PORTABLE_FOCAL {report["camera"]["focal"]}',
        f'#define PORTABLE_NEAR_Z {report["camera"]["near_z"]}',
        'extern const scene_mesh_t portable_meshes[];',
        'extern const game_asset_set_t portable_assets;',
        '#ifdef PORTABLE_DATA_DEFINE']
    if report['controller_present']:
        lines[-1:-1]=['extern const player_world_t portable_world;','extern const first_person_config_t portable_camera;']
    def array(typ,name,rows):
        storage='' if name=='portable_meshes' else 'static '
        declaration=name if '[' in name else name+'[]'
        lines.append(f'{storage}const PORTABLE_STORAGE {typ} {declaration}={{'+','.join(rows or ['{0}'])+'};')
    array('uint8_t','portable_palette[][3]',['{'+','.join(map(str,c))+'}' for c in palette])
    for h,(v,t) in enumerate(chunks):
        for typ,label,rows in (('scene_vertex_t','v',v),('scene_triangle_t','t',t)):
            array(typ,f'portable_{label}_{h}',['{'+','.join(map(str,p))+'}' for p in rows])
    array('scene_mesh_t','portable_meshes',[f'{{portable_v_{h},portable_t_{h},{len(v)},{len(t)}}}' for h,(v,t) in enumerate(chunks)])
    for typ,name,data in (('collision_floor_t','portable_floors',floors),('collision_wall_t','portable_walls',walls)):
        array(typ,name,['{'+','.join('{'+','.join(map(str,p))+'}' for p in pts)+','+','.join(map(str,rest))+'}' for pts,rest in data])
    if report['controller_present']:
        values=[len(floors),len(walls)]+report['spawn_q8_8']+[report['physics'][k] for k in PHYSICS]
        lines.append('const PORTABLE_STORAGE player_world_t portable_world={portable_floors,portable_walls,'+','.join(map(str,values))+'};')
        rotations=[[round(math.cos(i*math.tau/64)*256),round(math.sin(i*math.tau/64)*256)] for i in range(64)]
        array('int16_t','portable_rotations[][2]',['{'+','.join(map(str,r))+'}' for r in rotations])
        c=report['camera'];lines.append('const PORTABLE_STORAGE first_person_config_t portable_camera={portable_rotations,'+','.join(map(str,[c['initial_yaw'],c['eye_height'],c['region_radius']]))+'};')
    lines.append('const PORTABLE_STORAGE game_asset_set_t portable_assets={GAME_RUNTIME_ABI,portable_meshes,portable_meshes+PORTABLE_WORLD_MESHES,'+
        f'{report["world_meshes"]},{report["actor_meshes"]},portable_palette,{len(palette)}'+'};')
    lines+=['#endif','#endif',''];return '\n'.join(lines)

def project(path):
    path=path.resolve();spec=json.loads(path.read_text())
    if spec.get('format')!='soc-game-project' or type(spec.get('version')) is not int or spec['version']!=1:
        raise ValueError('Expected soc-game-project version 1')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',spec['name']):raise ValueError('Project name must be a lowercase filename-safe identifier')
    port=spec['port'];kind=port['kind']
    if kind=='scene-explorer':sources=[ROOT/'firmware/ports/scene_explorer.c'];api=[]
    elif kind=='custom':
        sources=[(path.parent/p).resolve() for p in port['sources']];api=port.get('exports',[])
        if not sources or any(p.suffix!='.c' or not p.is_relative_to(ROOT) or not p.is_file() for p in sources):
            raise ValueError('Custom port sources must be existing .c files inside the repository')
        if not isinstance(api,list) or any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',n) for n in api):
            raise ValueError('Port exports must be C identifiers; final link must resolve every symbol')
    else:raise ValueError('Choose scene-explorer or custom port')
    scene_path=(path.parent/spec['scene']).resolve();scene=json.loads(scene_path.read_text())
    if scene.get('format')=='soc-world-ir':
        if kind!='custom':raise ValueError('Multi-area worlds require an explicit custom port')
        from world_assets import compile_world
        result=compile_world(scene);compiled=result[:5];requirements=scene['resident_scene']['target']
    else:compiled=compile_scene(scene,kind=='scene-explorer');requirements=scene['target']
    if kind=='custom' and 'custom-rv32i-gameplay' not in requirements['required_features']:
        raise ValueError('Custom port must declare custom-rv32i-gameplay')
    return spec,scene_path,scene,compiled,sources,api

def generate(path):
    candidate=json.loads((path.parent/json.loads(path.read_text())['scene']).read_text())
    if candidate.get('format')=='soc-world-ir':
        from world_assets import generate as generate_world
        return generate_world(path)
    spec,scene_path,scene,compiled,sources,api=project(path)
    chunks,palette,floors,walls,report=compiled
    report['source_scene_sha256']=hashlib.sha256(scene_path.read_bytes()).hexdigest()
    report['project_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['game_port']={'kind':spec['port']['kind'],'sources':[
        {'file':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources],
        'declared_cross_file_exports':api}
    content=game_package.content(path,report,chunks)
    content['configuration']['game']={'port':spec['port']['kind']}
    (ROOT/'firmware/generated').mkdir(parents=True,exist_ok=True)
    (ROOT/'firmware/generated/portable_data.h').write_text(header(chunks,palette,floors,walls,report))
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/f'build/{spec["name"]}.conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    return spec,content,scene['target'],sources,api,report

def export_quake(pak,profile_path,destination):
    import quake_assets
    profile=json.loads(profile_path.read_text());chunks,palette,_,_,report=quake_assets.prepare(pak,profile)
    entries=quake_assets.pak_entries(pak.read_bytes());lumps=quake_assets.bsp_lumps(entries[profile['map']])
    source=list(struct.iter_unpack('<3f',lumps[3]));meshes=[]
    for h,((points,triangles),mapping) in enumerate(zip(chunks,report['chunk_source_triangles'])):
        original=[None]*len(points)
        for tri,record in zip(triangles,mapping):
            for index,source_id in zip(tri[:3],record['vertices']):original[index]=list(source[source_id])
        meshes.append({'id':f'world-{h}','role':'world','vertices':original,
            'triangles':[[t[0],t[2],t[1],t[3]] for t in triangles]})
    camera={**report['camera'],'initial_yaw':report['initial_yaw'],'region_radius':profile['selection_radius']*profile['scale']}
    scene={'format':'soc-scene-ir','version':1,'target':{'id':target_capabilities.target()['id'],'runtime_abi':1,
        'required_features':['indexed-flat-rgb','triangle-collision','first-person-controller']},
        'coordinates':{'origin':report['source_origin'],'scale':profile['scale'],'axes':[1,3,2]},
        'palette':[list(p) for p in palette],'meshes':meshes,
        'controller':{'spawn':report['source_origin'],'physics':report['physics'],'camera':camera},
        'provenance':{'adapter':'quake-bsp29','map':profile['map'],'map_sha256':report['map_sha256'],
            'pak_sha256':report['pak_sha256'],'selection_profile_sha256':hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            'source_face_selection':report['selected_face_ids'],'omissions_before_ir':report['omissions'],
            'appearance_policy':report['appearance_policy'],'original_engine_ported':False}}
    # Validate before writing. The exporter makes the explicit source selection;
    # the shared compiler never performs hidden selection/simplification.
    compile_scene(scene)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(scene,indent=2)+'\n')
    proj=destination.with_name(destination.stem+'.project.json')
    proj.write_text(json.dumps({'format':'soc-game-project','version':1,'name':'portable-quake',
        'scene':destination.name,'port':{'kind':'scene-explorer'}},indent=2)+'\n')
    print('Exported original Quake scene IR and project:',proj)

def export_obj(source,destination,name,extent,spawn):
    import scene_assets
    # Existing OBJ adapter supports triangulated geometry and flat Kd materials.
    # Reject texture-bearing inputs rather than silently erasing their requirements.
    materials=[]
    for raw in source.read_text().splitlines():
        fields=raw.split('#',1)[0].split()
        if fields and fields[0]=='mtllib':materials += [(source.parent/p).resolve() for p in fields[1:]]
    for material in materials:
        for raw in material.read_text().splitlines():
            fields=raw.split('#',1)[0].split()
            if fields and (fields[0].startswith('map_') or fields[0] in ('bump','disp','decal')):
                raise ValueError('OBJ material needs unsupported textures; use an explicit source-specific baking adapter')
            if fields and fields[0] in ('d','Tr') and number(float(fields[1])) != (1 if fields[0]=='d' else 0):
                raise ValueError('OBJ material needs unsupported alpha blending')
    palette,chunks=scene_assets.convert(source,extent_q8_8=extent)
    floors,_=game_assets.collision(chunks)
    floor=game_assets.floor_height(floors,spawn[0],spawn[2],spawn[1]+36)
    if floor==-32768:raise ValueError('No floor at requested normalized spawn; select a walkable area or write a custom scene/game port')
    scene={'format':'soc-scene-ir','version':1,'target':{'id':target_capabilities.target()['id'],'runtime_abi':1,
        'required_features':['indexed-flat-rgb','triangle-collision','first-person-controller']},
        'coordinates':{'origin':[0,0,0],'scale':1,'axes':[1,2,3]},'palette':[list(p) for p in palette],
        'meshes':[{'id':f'world-{h}','role':'world','vertices':[list(p) for p in v],
                   'triangles':[list(p) for p in t]} for h,(v,t) in enumerate(chunks)],
        'controller':{'spawn':[spawn[0],floor,spawn[2]],
          'physics':{'speed':12,'radius':32,'height':112,'step_height':36,'gravity':2,'jump_speed':18,'kill_y':-8192},
          'camera':{'eye_height':92,'focal':160,'near_z':257,'initial_yaw':0,'region_radius':8192}},
        'provenance':{'adapter':'triangulated-obj','obj_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'material_files':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in materials],
          'normalization_extent_gpu_units':extent,'input_axes':'Y-up, outward winding',
          'appearance_policy':'existing OBJ adapter: flat Kd RGB with directional face shading; textures/alpha rejected',
          'coordinate_policy':'existing OBJ adapter: center referenced bounds and uniformly scale the largest extent',
          'spawn_policy':'supporting floor at requested normalized X/Z below requested Y+36',
          'original_engine_ported':False}}
    compile_scene(scene)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}',name):raise ValueError('Invalid project name')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(scene,indent=2)+'\n')
    project_path=destination.with_name(destination.stem+'.project.json')
    project_path.write_text(json.dumps({'format':'soc-game-project','version':1,'name':name,
        'scene':destination.name,'port':{'kind':'scene-explorer'}},indent=2)+'\n')
    print('Exported generic OBJ scene IR and project:',project_path)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('check');p.add_argument('project',type=Path)
    p=sub.add_parser('export-quake');p.add_argument('--pak',type=Path,default=ROOT/'build/quake-shareware/pak0.pak')
    p.add_argument('--profile',type=Path,default=ROOT/'profiles/quake-e1m1.json')
    p.add_argument('--out',type=Path,default=ROOT/'build/quake.scene-ir.json')
    p=sub.add_parser('export-obj');p.add_argument('--obj',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--name',default='portable-obj')
    p.add_argument('--extent',type=int,default=2048)
    p.add_argument('--spawn',type=int,nargs=3,default=[0,0,0],metavar=('X','Y','Z'))
    args=parser.parse_args()
    try:
        if args.command=='export-quake':export_quake(args.pak,args.profile,args.out)
        elif args.command=='export-obj':export_obj(args.obj,args.out,args.name,args.extent,args.spawn)
        else:
            spec,_,scene,compiled,_,_=project(args.project)
            report=compiled[-1]
            print(json.dumps({'compatible_scene':True,'project':spec['name'],'resident_handles':report['meshes'],
                'triangles':report['source_triangles'],'maximum_quantization_error_gpu_units':report['maximum_quantization_error_gpu_units'],
                'engine_port_audited':False,'streaming':scene.get('format')=='soc-world-ir',
                'areas':report.get('areas',1),'stored_world_chunks':report.get('stored_world_chunks',report['world_meshes'])},indent=2))
    except (KeyError,TypeError,ValueError,OSError) as exc:parser.exit(1,'ERROR: '+str(exc)+'\n')

if __name__=='__main__':main()
