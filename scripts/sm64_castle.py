"""Pinned SM64 castle/slide source adapter. Emits the reusable SDRAM world IR."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import animation_assets
import game_assets
import scene_assets
import sm64_subset

ROOT=Path(__file__).resolve().parents[1]
AREAS=[('castle_grounds',1,'castle_geo_ground'),('castle_inside',1,'castle_ground_floor'),
       ('castle_inside',2,'castle_upper_floor'),('castle_inside',3,'castle_basement'),('pss',1,'secret_slide')]
SPAWNS=[[-1328,260,4664],[-1023,0,1152],[-1023,512,2850],[-1023,-1074,800],[5632,6451,-5631]]

def clean(text):return re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
def integer(s):
    if not re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|\d+)',s.strip()):raise ValueError('Expected source integer literal: '+s)
    return int(s,16 if 'x' in s.lower() else 10)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def region(text):
    """Select VERSION_US literally; reject unsupported preprocessing directives."""
    # Texture payloads are replaced by the declared flat-color policy. Only
    # includes inside Texture arrays may be omitted; geometry includes fail.
    text=re.sub(r'(\bconst\s+Texture\s+\w+\s*\[\]\s*=\s*\{)(.*?)(\};)',
        lambda m:m[1]+re.sub(r'^\s*#include "levels/[\w/]+\.(?:rgba16|ia8)\.inc\.c"\s*$','',m[2],flags=re.M)+m[3],text,flags=re.S)
    enabled=True;stack=[];output=[]
    for line in text.splitlines():
        directive=line.strip()
        if directive.startswith('#ifdef '):
            name=directive.split()[1]
            if name not in ('VERSION_US','VERSION_JP','VERSION_EU','VERSION_SH'):raise ValueError('Unsupported region conditional '+name)
            condition=name=='VERSION_US';stack.append((enabled,condition));enabled=enabled and condition
        elif directive=='#else':
            if not stack:raise ValueError('Unmatched source #else')
            parent,condition=stack[-1];enabled=parent and not condition
        elif directive=='#endif':
            if not stack:raise ValueError('Unmatched source #endif')
            enabled=stack.pop()[0]
        elif directive.startswith('#'):raise ValueError('Unsupported source directive '+directive)
        elif enabled:output.append(line)
    if stack:raise ValueError('Unclosed source conditional')
    return '\n'.join(output)

def collision(path,room_path=None,surface_types=None):
    text=clean(path.read_text());vertices=[];triangles=[];forces=[];kind=None;expected=0;seen=0;declared=None;objects=[];water=[]
    for name,args in sm64_subset.calls(re.search(r'=\s*\{(.*?)\};',text,re.S)[1],r'[A-Z_]+'):
        if name=='COL_VERTEX_INIT':declared=integer(args[0])
        elif name=='COL_VERTEX':vertices.append([integer(a) for a in args])
        elif name=='COL_TRI_INIT':
            if kind is not None and expected!=seen:raise ValueError('Source collision group count mismatch')
            kind=args[0];expected=integer(args[1]);seen=0
        elif name in ('COL_TRI','COL_TRI_SPECIAL'):
            if kind is None:raise ValueError('Collision triangle before surface group')
            triangles.append([*(integer(a) for a in args[:3]),kind,0]);seen+=1
            force=integer(args[3]) if name=='COL_TRI_SPECIAL' else 0
            if not -32768<=force<=65535:raise ValueError('Source collision force exceeds 16 bits')
            forces.append(force-65536 if force>32767 else force)
        elif name=='COL_TRI_STOP':
            if expected!=seen:raise ValueError('Source final collision group count mismatch')
        elif name.startswith('SPECIAL_OBJECT'):
            objects.append({'preset':args[0],'position':[integer(a) for a in args[1:4]],
                'yaw':integer(args[4]) if len(args)>4 else 0,'parameter':integer(args[5]) if len(args)>5 else None})
        elif name=='COL_WATER_BOX':water.append([integer(a) for a in args])
        elif name not in ('COL_INIT','COL_END','COL_SPECIAL_INIT','COL_WATER_BOX_INIT'):
            raise ValueError('Unsupported original collision command '+name)
    if declared!=len(vertices):raise ValueError('Source collision vertex count mismatch')
    if room_path and room_path.exists():
        room_body=re.search(r'=\s*\{(.*?)\};',clean(room_path.read_text()),re.S)[1]
        rooms=[integer(s) for s in room_body.split(',') if s.strip()]
        if len(rooms)!=len(triangles):raise ValueError('Room table does not cover every collision surface')
        for t,room in zip(triangles,rooms):t[4]=room
    result={'vertices':vertices,'triangles':triangles,'triangle_forces':forces,'special_objects':objects,'water_boxes':water,'source':path.as_posix(),'sha256':digest(path)}
    if surface_types is not None:
        names={t[3] for t in triangles}
        if names-surface_types.keys():raise ValueError('Unknown original surface type: '+str(names-surface_types.keys()))
        result['surface_types']={name:surface_types[name] for name in sorted(names)}
    return result

def surface_types(source):
    text=clean((source/'include/surface_terrains.h').read_text())
    return {name:integer(value) for name,value in re.findall(r'^#define\s+(SURFACE_\w+)\s+(0x[0-9A-Fa-f]+|\d+)\s*$',text,re.M)}

def level_nodes(source,level):
    """Resolve source-local script calls; never run source C/preprocessor code."""
    path=source/'levels'/level/'script.c';text=clean(path.read_text())
    scripts=dict(re.findall(r'(?:static\s+)?const LevelScript (\w+)\[\]\s*=\s*\{(.*?)\};',text,re.S))
    result={};area=None;stack=[]
    def visit(name):
        nonlocal area
        if name in stack:raise ValueError('Cyclic level script')
        stack.append(name)
        for command,args in sm64_subset.calls(scripts[name],r'[A-Z_][A-Z_0-9]*'):
            if command=='AREA':area=integer(args[0]);result[area]={'objects':[],'warps':{}}
            elif command=='END_AREA':area=None
            elif command=='JUMP_LINK' and args[0] in scripts:visit(args[0])
            elif area is not None and command=='WARP_NODE':
                result[area]['warps'][integer(args[0])]=[args[1],integer(args[2]),integer(args[3])]
            elif area is not None and command=='OBJECT' and ('Warp' in args[-1] or args[-1]=='bhvWarp'):
                result[area]['objects'].append({'model':args[0],'position':[integer(a) for a in args[1:4]],
                    'yaw':round(integer(args[5])*256/360)&255,'parameter':integer(args[7]),'behavior':args[8]})
        stack.pop()
    visit(next(n for n in scripts if n.startswith('level_') and n.endswith('_entry')))
    return result

def transitions(source,areas):
    levels={'castle_grounds':'LEVEL_CASTLE_GROUNDS','castle_inside':'LEVEL_CASTLE','pss':'LEVEL_PSS'}
    nodes={level:level_nodes(source,level) for level in levels};lookup={};objects={}
    for index,a in enumerate(areas):
        key=(levels[a['source_level']],a['source_area']);lookup[key]=index
        records=nodes[a['source_level']][a['source_area']]['objects'][:]
        for o in a['collision']['special_objects']:
            if o['parameter'] is not None and o['preset'].endswith('_door_warp'):
                records.append({'model':o['preset'],'position':o['position'],'yaw':o['yaw'],
                    'parameter':o['parameter']<<16,'behavior':'bhvDoorWarp'})
        objects[key]=records
    output=[];unsupported=[]
    for key,records in objects.items():
        source_area=lookup[key];a=areas[source_area];warps=nodes[a['source_level']][a['source_area']]['warps']
        for o in records:
            # Arrival-only objects are nodes, not active teleport triggers.
            if o['behavior'] not in ('bhvDoorWarp','bhvWarp'):continue
            node=(o['parameter']>>16)&255
            if node not in warps:raise ValueError('Active source warp has no WARP_NODE')
            level,number,destination=warps[node];destkey=(level,number)
            if destkey not in lookup:
                unsupported.append({'source_area':source_area,'node':node,'destination':warps[node]});continue
            matches=[d for d in objects[destkey] if (d['parameter']>>16)&255==destination]
            dest=next((d for d in matches if d['behavior']=='bhvDoorWarp'),None) if o['behavior']=='bhvDoorWarp' else next(iter(matches),None)
            if dest is None:raise ValueError('Original warp destination has no spawn object')
            arrival=dest['position'][:]
            # Original init_door_warp applies a 300-unit forward displacement.
            if dest['behavior']=='bhvDoorWarp':
                angle=dest['yaw']*math.tau/256
                arrival[0]+=round(300*math.sin(angle));arrival[2]+=round(300*math.cos(angle))
            output.append({'source_area':source_area,'destination_area':lookup[destkey],
                'position':o['position'],'arrival':arrival,'radius':150 if o['behavior']=='bhvDoorWarp' else 50,
                'required_stars':0,'required_keys':(o['parameter']>>24)&3 if o['model']=='MODEL_CASTLE_KEY_DOOR' else 0,
                'yaw':dest['yaw'],'automatic':o['behavior']=='bhvWarp','source_node':node,'destination_node':destination})
    return output,unsupported

def event_exits(source,areas):
    """Original script exits used by star collection, death and falling floors.

    These are event destinations, never positional triggers. Shared runtime
    treats the source node ID as an opaque event supplied by the game port.
    """
    levels={'castle_grounds':'LEVEL_CASTLE_GROUNDS','castle_inside':'LEVEL_CASTLE','pss':'LEVEL_PSS'}
    nodes={level:level_nodes(source,level) for level in levels}
    lookup={(levels[a['source_level']],a['source_area']):i for i,a in enumerate(areas)}
    result=[]
    for i,a in enumerate(areas):
        for event,destination in nodes[a['source_level']][a['source_area']]['warps'].items():
            if event not in (0xF0,0xF1,0xF3):continue
            level,number,node=destination
            if (level,number) not in lookup:continue
            index=lookup[(level,number)];target=areas[index]
            objects=nodes[target['source_level']][number]['objects']
            matches=[o for o in objects if (o['parameter']>>16)&255==node]
            if len(matches)!=1:raise ValueError('Event exit destination must identify one source spawn object')
            spawn=matches[0]
            result.append({'source_area':i,'event':event,'destination_area':index,
                'arrival':spawn['position'],'yaw':spawn['yaw'],'destination_node':node,
                'spawn_behavior':spawn['behavior']})
    return result

def actor(source,palette):
    profile=json.loads((ROOT/'profiles/sm64-mario-sdram.json').read_text());policy=profile['actor']
    text=(source/policy['source']).read_text();points=[];local_points=[];parts=[];faces=[];reports=[]
    for part in policy['parts']:
        pts,fs,commands,discarded=sm64_subset.lower(text,{**policy,'display_list':part['display_list'],'initial_light':part['light']})
        local_points.extend(pts);parts.append((part,pts));offset=len(points);r=part['rotation'];tr=part['translation']
        for p in pts:
            q=[sum(r[3*i+j]*p[j] for j in range(3))+tr[i] for i in range(3)];points.append((q[2],q[0],q[1]))
        faces.extend(([i+offset for i in f],m) for f,m in fs)
        reports.append({'display_list':part['display_list'],'triangles':len(fs),'discarded':discarded})
    path=ROOT/'build/castle/actor.obj';game_assets.write_obj(path,points,faces,{**policy['light_colors'],**policy['texture_colors']})
    low=min(p[1] for p in points);high=max(p[1] for p in points);center=[(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)]
    palette,chunks=scene_assets.convert(path,transform=lambda p:((p[0]-center[0])*180/(high-low),(p[1]-low)*180/(high-low),(p[2]-center[2])*180/(high-low)),palette=palette)
    chunks,lines,report=animation_assets.prepare(source,{**profile['animation'],'height':180},parts,local_points,faces,chunks)
    lines=[s.replace('actor_meshes','portable_meshes') for s in lines]
    (ROOT/'firmware/generated/castle_actor_data.h').write_text('#ifndef CASTLE_ACTOR_DATA_H\n#define CASTLE_ACTOR_DATA_H\n#include "portable_data.h"\n'+
        '\n'.join(lines).replace('static const ','static const __attribute__((section(".game_assets"))) ')+
        '\nstatic const __attribute__((section(".game_assets"))) int16_t castle_rotations[256][2]={'+
        ','.join('{%d,%d}'%(round(math.cos(i*math.tau/256)*256),round(math.sin(i*math.tau/256)*256)) for i in range(256))+'};\n#endif\n')
    return palette,[{'id':'player-'+str(i),'role':'actor','vertices':[list(p) for p in v],
        'triangles':[list(t) for t in ts],'retain_degenerate_actor_faces':True} for i,(v,ts) in enumerate(chunks)],report

def flat_policy(text):
    textures=set(re.findall(r'gsDPSetTextureImage\([^)]*,\s*(\w+)\s*\)',text))
    textures.update(re.findall(r'gsDPLoadTextureBlock\(\s*(\w+)',text))
    # Explicit authored approximations; missing source texture pixels cannot
    # be recovered from the source symbols. Never silently turn new materials gray.
    profile=json.loads((ROOT/'profiles/sm64-castle-colors.json').read_text())
    if profile.get('format')!='soc-flat-material-profile' or profile.get('version')!=1:
        raise ValueError('Invalid castle flat-material profile')
    if profile['source_commit']!=json.loads((ROOT/'sm64.lock.json').read_text())['commit']:
        raise ValueError('Castle colors must be reviewed for the pinned source commit')
    colors=profile['colors'];materials=profile['materials'];base={}
    for name,swatch in materials.items():
        if swatch not in colors:raise ValueError('Unknown material color '+swatch)
        rgb=colors[swatch]
        if not isinstance(rgb,list) or len(rgb)!=3 or any(type(v) is not int or not 0<=v<=255 for v in rgb):
            raise ValueError('Material colors require three integer RGB bytes')
        base[name]=[v/255 for v in rgb]
    missing=(textures|{'default'})-base.keys()
    if missing:raise ValueError('Declare castle flat colors for '+', '.join(sorted(missing)))
    return {'discard_state':sorted(sm64_subset.DISCARDABLE_STATE),
        'texture_colors':{name:base[name] for name in sorted(textures|{'default'})},
        'opaque_environment':True,'alpha_as_solid':True,'flat_texture_block':True}

def geometry(source,level,area,palette):
    directory=source/'levels'/level/'areas'/str(area)
    geo=clean((directory/'geo.inc.c').read_text())
    # Branches retain source identities. All room geometry is stored; runtime visibility is separate.
    layouts=dict(re.findall(r'const GeoLayout (\w+)\[\]\s*=\s*\{(.*?)\};',geo,re.S))
    branches=re.findall(r'GEO_BRANCH\(1,\s*(\w+)\)',next((b for b in layouts.values() if 'geo_switch_area' in b),''))
    masks={}
    for room,branch in enumerate(branches,1):
        if branch not in layouts:raise ValueError('Unresolved room GeoLayout '+branch)
        for layer,root in re.findall(r'GEO_DISPLAY_LIST\(\s*(LAYER_\w+)\s*,\s*(\w+)\s*\)',layouts[branch]):
            masks[(layer,root)]=masks.get((layer,root),0)|(1<<(room-1))
    roots=list(masks) if branches else list(dict.fromkeys(re.findall(r'GEO_DISPLAY_LIST\(\s*(LAYER_\w+)\s*,\s*(\w+)\s*\)',geo)))
    files=sorted(directory.rglob('model.inc.c'))
    painting=source/'levels'/level/'painting.inc.c'
    if painting.is_file():files.append(painting)
    text=region('\n'.join(p.read_text().replace('#include "game/paintings.h"','') if p==painting else p.read_text() for p in files));policy=flat_policy(text)
    vertices=[];triangles=[];root_reports=[];triangle_rooms=[]
    for layer,root in roots:
        p,fs,commands,discarded=sm64_subset.lower(text,{**policy,'display_list':root})
        offset=len(vertices);vertices.extend([list(v) for v in p])
        for f,material in fs:
            if material not in policy['texture_colors']:raise ValueError('Unmapped rendered castle material '+material)
            rgb=tuple(round(v*255) for v in policy['texture_colors'][material])
            if rgb not in palette:
                if len(palette)>=256:raise ValueError('Explicit castle flat palette exceeds target capacity')
                palette.append(rgb)
            triangles.append([*(i-1+offset for i in f),palette.index(rgb)])
            triangle_rooms.append(masks.get((layer,root),0))
        root_reports.append({'root':root,'layer':layer,'triangles':len(fs),'commands':commands,'discarded_appearance':discarded})
    return vertices,triangles,{'geo_sha256':digest(directory/'geo.inc.c'),'triangle_room_masks':triangle_rooms,
        'room_branches':branches,
        'sources':[{'file':p.relative_to(source).as_posix(),'sha256':digest(p)} for p in files],
        'roots':root_reports,'flat_texture_colors':policy['texture_colors'],
        'material_profile':{'file':'profiles/sm64-castle-colors.json','sha256':digest(ROOT/'profiles/sm64-castle-colors.json')},
        'appearance_policy':'declared-flat-colors; texture alpha/decal appearance rendered solid; geometry retained'}

def export(destination):
    source=sm64_subset.fetch();destination.mkdir(parents=True,exist_ok=True);(ROOT/'build/castle').mkdir(parents=True,exist_ok=True)
    palette=[(100,170,230)];palette,actors,animation=actor(source,palette);areas=[];types=surface_types(source)
    for index,(level,number,name) in enumerate(AREAS):
        vertices,triangles,provenance=geometry(source,level,number,palette)
        area_dir=source/'levels'/level/'areas'/str(number)
        areas.append({'id':name,'vertices':vertices,'triangles':triangles,'spawn':SPAWNS[index],
            'triangle_room_masks':provenance.pop('triangle_room_masks'),
            'collision':collision(area_dir/'collision.inc.c',area_dir/'room.inc.c',types),
            'provenance':provenance,'source_level':level,'source_area':number})
    target={'id':'de2-115-fixed-v2','runtime_abi':1,'required_features':['indexed-flat-rgb','triangle-collision','custom-rv32i-gameplay','mouse-look-v1']}
    resident={'format':'soc-scene-ir','version':1,'target':target,'coordinates':{'origin':[0,0,0],'scale':1,'axes':[1,2,3]},
        'palette':[list(c) for c in palette],'meshes':actors,'projection':{'focal':256,'near_z':257},
        'provenance':{'adapter':'sm64-castle','source_commit':json.loads((ROOT/'sm64.lock.json').read_text())['commit']}}
    world={'format':'soc-world-ir','version':1,'resident_scene':resident,'areas':areas,
        'implementation_status':'castle-traversal-foundation; mission incomplete',
        'mission':{'name':'Peachs Secret Slide box star','source_position':[-6385,-4200,5770],
            'save_fixture':{'course_stars':70,'castle_keys':2,'slide_box_star':False}},'animation':animation}
    world['transitions'],world['unsupported_transitions']=transitions(source,areas)
    world['event_exits']=event_exits(source,areas)
    lines=['#ifndef CASTLE_TRANSITIONS_H','#define CASTLE_TRANSITIONS_H','#include "world.h"',
        'static const __attribute__((section(".game_assets"))) world_transition_t castle_transitions[]={']
    for t in world['transitions']:
        lines.append('{%d,%d,{%s},{%s},%d,%d,%d,%d,%d},'%(t['source_area'],t['destination_area'],','.join(map(str,t['position'])),
            ','.join(map(str,t['arrival'])),t['radius'],t['required_stars'],t['required_keys'],t['yaw'],t['automatic']))
    lines+=['};',f'#define CASTLE_TRANSITION_COUNT {len(world["transitions"])}u',
        'static const __attribute__((section(".game_assets"))) world_exit_t castle_exits[]={']
    for t in world['event_exits']:
        lines.append('{%d,%d,%d,{%s},%d},'%(t['source_area'],t['event'],t['destination_area'],','.join(map(str,t['arrival'])),t['yaw']))
    lines+=['};',f'#define CASTLE_EXIT_COUNT {len(world["event_exits"])}u',
        '#define CASTLE_EXIT_STAR 0xF0u','#define CASTLE_EXIT_DEATH 0xF1u','#define CASTLE_EXIT_FALL 0xF3u']
    lines+=['#endif']
    (ROOT/'firmware/generated/castle_transitions.h').write_text('\n'.join(lines)+'\n')
    (ROOT/'firmware/generated/castle_surface_types.h').write_text('#ifndef CASTLE_SURFACE_TYPES_H\n#define CASTLE_SURFACE_TYPES_H\n'+
        '\n'.join('#define CASTLE_'+name+' '+str(value)+'u' for name,value in sorted(types.items()))+'\n#endif\n')
    path=destination/'world.json';path.write_text(json.dumps(world,indent=2)+'\n')
    project={'format':'soc-game-project','version':1,'name':'mario-castle','scene':'world.json',
        'port':{'kind':'custom','sources':[os.path.relpath(ROOT/'firmware/ports/castle.c',destination).replace('\\','/'),
            os.path.relpath(ROOT/'firmware/ports/castle_rules.c',destination).replace('\\','/'),
            os.path.relpath(ROOT/'firmware/src/world.c',destination).replace('\\','/'),
            os.path.relpath(ROOT/'firmware/src/camera.c',destination).replace('\\','/'),
            os.path.relpath(ROOT/'firmware/src/animation.c',destination).replace('\\','/'),
            os.path.relpath(ROOT/'firmware/src/game_services.c',destination).replace('\\','/')],
            'exports':['world_select','world_collision','world_floor_contact','world_exit_find','world_prepare','world_draw','world_transition_find','world_areas','player_bind_query','player_floor_index','camera_boom','camera_orbit_step','castle_floor_event']}}
    (destination/'game.project.json').write_text(json.dumps(project,indent=2)+'\n')
    print('Exported original castle/slide geometry and collision:',path)
    for a in areas:print(a['id'],len(a['triangles']),'render triangles',len(a['collision']['triangles']),'original collision faces')
    return world

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'build/castle')
    args=parser.parse_args();export(args.out.resolve())
if __name__=='__main__':main()
