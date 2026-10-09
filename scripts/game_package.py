"""Source-independent package metadata and an original fixed-point scene adapter."""
import hashlib
import json
import math
from pathlib import Path
import game_assets

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ABI = 1

def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Expected integer in [{low},{high}]')
    return value

def mesh(source, palette_count):
    kind=source['kind']
    if kind=='floor':
        x0,x1,y,z0,z1=source['bounds']
        if x0>=x1 or z0>=z1: raise ValueError('Empty floor bounds')
        vertices=[(x0,y,z0),(x1,y,z0),(x1,y,z1),(x0,y,z1)]
        triangles=[(0,3,2,source['color']),(0,2,1,source['color'])]
    elif kind=='box':
        x0,x1,y0,y1,z0,z1=source['bounds']
        if x0>=x1 or y0>=y1 or z0>=z1 or len(source['colors'])!=6:
            raise ValueError('Empty box or missing face colors')
        vertices=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                  (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        faces=((0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4))
        triangles=[tri+(color,) for face,color in zip(faces,source['colors'])
                   for tri in ((face[0],face[1],face[2]),(face[0],face[2],face[3]))]
    elif kind=='diamond':
        radius=integer(source['radius'],1,256); height=integer(source['height'],2,512)
        vertices=[(0,height,0),(radius,height//2,0),(0,height//2,radius),
                  (-radius,height//2,0),(0,height//2,-radius),(0,0,0)]
        triangles=[tri+(source['color'],) for i in range(4)
                   for tri in ((0,1+(i+1)%4,1+i),(5,1+i,1+(i+1)%4))]
    else: raise ValueError('Unsupported authored mesh kind')
    for vertex in vertices:
        for coordinate in vertex: integer(coordinate,-8192,8192)
    for triangle in triangles: integer(triangle[3],0,palette_count-1)
    return vertices,triangles

def validate_content(content):
    if not isinstance(content,dict) or content.get('format')!='soc-game-assets' or type(content.get('version')) is not int or content.get('version')!=1:
        raise ValueError('Unsupported game content schema')
    if type(content.get('runtime_abi')) is not int or content.get('runtime_abi')!=RUNTIME_ABI or content.get('units')!='gpu-q8.8':
        raise ValueError('Unsupported game runtime or coordinate ABI')
    if content.get('material_policy')!='indexed-flat-rgb': raise ValueError('Unsupported material policy')
    palette=integer(content['palette_colors'],1,256)
    meshes=content['meshes']
    if not isinstance(meshes,list) or not 1<=len(meshes)<=16: raise ValueError('GPU handle capacity')
    for item in meshes:
        integer(item['vertices'],1,128); integer(item['triangles'],1,256)
    collision=content['collision']
    if collision.get('abi')!='triangle-q12-normal-v1': raise ValueError('Unsupported collision ABI')
    integer(collision['floors'],0,16384); integer(collision['walls'],0,16384)
    animation=content['animation']
    if animation.get('abi') not in ('none','indexed-joints-q14-v1'): raise ValueError('Unsupported animation ABI')
    if not isinstance(animation.get('clips'),list): raise ValueError('Missing animation clips')
    configuration=content.get('configuration')
    if not isinstance(configuration,dict) or not all(key in configuration for key in ('module','physics','camera','spawn','game')):
        raise ValueError('Missing game configuration')
    if not isinstance(content.get('game'),str) or not content['game']: raise ValueError('Missing game identity')
    source=content.get('source',{})
    if not isinstance(source.get('profile'),str) or not isinstance(source.get('sha256'),str) or len(source['sha256'])!=64 or any(ch not in '0123456789abcdef' for ch in source['sha256']):
        raise ValueError('Missing source provenance')
    return palette

def content(profile_path, report, chunks):
    profile=json.loads(profile_path.read_text())
    animation=report.get('animation')
    result={'format':'soc-game-assets','version':1,'runtime_abi':RUNTIME_ABI,
            'game':profile['name'],'units':'gpu-q8.8','material_policy':'indexed-flat-rgb',
            'palette_colors':report['palette_colors'],
            'meshes':[{'vertices':len(v),'triangles':len(t)} for v,t in chunks],
            'collision':{'abi':'triangle-q12-normal-v1','floors':report['collision_floors'],'walls':report['collision_walls']},
            'animation':{'abi':'indexed-joints-q14-v1' if animation else 'none',
                         'clips':list(profile.get('animation',{}).get('clips',{}))},
            'configuration':{'module':report.get('module','mario'),'physics':report['physics'],
                             'camera':report['camera'],'spawn':report['spawn_q8_8'],
                             'game':profile.get('game',{})},
            'source':{'profile':profile_path.name,'sha256':hashlib.sha256(profile_path.read_bytes()).hexdigest()}}
    validate_content(result)
    return result

def mario_content(profile_path, report):
    # Count packed mesh records emitted by the source-specific SM64 adapter.
    import re
    header=(ROOT/'firmware/generated/game_data.h').read_text()
    counts=re.findall(r'\{(?:world|actor)_vertices_\d+,(?:world|actor)_triangles_\d+,(\d+),(\d+)\}',header)
    chunks=[([None]*int(v),[None]*int(t)) for v,t in counts]
    if len(chunks)!=report['meshes']: raise ValueError('Generated mesh descriptor mismatch')
    return content(profile_path,report,chunks)

def generate(profile_path):
    profile_path=profile_path.resolve(); p=json.loads(profile_path.read_text())
    if p.get('format')!='soc-source-game' or p.get('version')!=1 or p.get('module')!='beacon' or p.get('units')!='gpu-q8.8':
        raise ValueError('Unsupported authored game profile')
    if p.get('appearance')!={'policy':'indexed-flat-rgb','textures':False,'alpha':False}:
        raise ValueError('Unsupported appearance capabilities')
    palette=p['palette']; integer(len(palette),1,256)
    for color in palette:
        if len(color)!=3: raise ValueError('RGB requires three channels')
        for value in color: integer(value,0,255)
    world=[mesh(item,len(palette)) for item in p['world']]
    actors=[mesh(item,len(palette)) for item in p['actors']]
    if not world or len(actors)!=2 or len(world)+len(actors)>16: raise ValueError('Scene handle layout')
    physics=p['physics']
    limits={'speed':(1,32),'radius':(4,64),'height':(32,256),'step_height':(0,64),
            'gravity':(1,16),'jump_speed':(1,96),'kill_y':(-8192,-1)}
    if set(physics)!=set(limits): raise ValueError('Unknown physics fields')
    for key,(lo,hi) in limits.items(): integer(physics[key],lo,hi)
    floors,walls=game_assets.collision(world); surfaces=game_assets.camera_surfaces(world)
    spawn=p['spawn']
    if len(spawn)!=3: raise ValueError('Spawn needs three coordinates')
    for value in spawn: integer(value,-8192,8192)
    if game_assets.floor_height(floors,spawn[0],spawn[2],spawn[1]+physics['step_height'])!=spawn[1]:
        raise ValueError('Spawn must be on a visible floor')
    camera=game_assets.camera_settings(p)
    beacons=p['game']['beacons']; integer(len(beacons),1,31)
    integer(p['game']['collect_radius'],1,256); integer(p['game']['collect_height'],1,256)
    for point in beacons:
        if len(point)!=3: raise ValueError('Beacon needs three coordinates')
        for value in point: integer(value,-8192,8192)
        if game_assets.floor_height(floors,point[0],point[2],point[1])!=point[1]:
            raise ValueError('Beacon must be above a visible floor')
    lines=['// Original authored package; no upstream models modified.','#ifndef BEACON_DATA_H','#define BEACON_DATA_H',
           '#include "assets.h"','#include "camera.h"','#include "beacon.h"',
           '#ifdef GAME_USE_SDRAM','#define GAME_STORAGE __attribute__((section(".game_assets")))',
           '#else','#define GAME_STORAGE','#endif',
           f'#define GAME_WORLD_MESHES {len(world)}u',f'#define GAME_MESH_COUNT {len(world)+len(actors)}u',
           f'#define GAME_PALETTE_COUNT {len(palette)}u',
           'static const uint8_t game_palette[][3]={'+','.join('{'+','.join(map(str,c))+'}' for c in palette)+'};']
    for name,chunks in (('world',world),('actor',actors)):
        for i,(v,t) in enumerate(chunks):
            for label,values,typ in (('vertices',v,'scene_vertex_t'),('triangles',t,'scene_triangle_t')):
                lines.append(f'static const {typ} {name}_{label}_{i}[]={{'+','.join('{'+','.join(map(str,x))+'}' for x in values)+'};')
        lines.append(f'static const scene_mesh_t {name}_meshes[]={{'+','.join(
            f'{{{name}_vertices_{i},{name}_triangles_{i},{len(v)},{len(t)}}}' for i,(v,t) in enumerate(chunks))+'};')
    for name,data,typ in (('floors',floors,'collision_floor_t'),('walls',walls,'collision_wall_t'),('camera_surfaces',surfaces,'collision_wall_t')):
        rows=['{'+','.join('{'+','.join(map(str,pt))+'}' for pt in pts)+','+','.join(map(str,rest))+'}' for pts,rest in data]
        lines.append(f'static const {typ} game_{name}[]={{'+','.join(rows or ['{0}'])+'};')
    settings=spawn+[physics[key] for key in limits]
    lines.append('static const player_world_t game_world={game_floors,game_walls,'+','.join(map(str,[len(floors),len(walls)]+settings))+'};')
    pitches=camera['pitches']+[[0,0]]*(4-len(camera['pitches']))
    lines.append('static const camera_config_t game_camera_config={'+','.join(map(str,[camera[k] for k in game_assets.CAMERA_FIELDS]+[len(camera['pitches'])]))+',{'+','.join('{'+','.join(map(str,x))+'}' for x in pitches)+'}};')
    lines.append(f'static const camera_world_t game_camera_world={{game_camera_surfaces,{len(surfaces)}}};')
    lines.append('static const int16_t game_beacon_positions[][3]={'+','.join('{'+','.join(map(str,x))+'}' for x in beacons)+'};')
    lines.append('static const beacon_config_t game_beacon_config={game_beacon_positions,'+','.join(map(str,[len(beacons),p['game']['collect_radius'],p['game']['collect_height']]))+'};')
    lines+=['#endif','']
    destination=ROOT/'firmware/generated/beacon_data.h'; destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text('\n'.join(lines).replace('static const ','static const GAME_STORAGE '))
    report={'module':'beacon','profile':p['name'],'palette_colors':len(palette),'meshes':len(world)+len(actors),
            'world_triangles':sum(len(t) for _,t in world),'actor_triangles':sum(len(t) for _,t in actors),
            'collision_floors':len(floors),'collision_walls':len(walls),'spawn_q8_8':spawn,'physics':physics,'camera':camera}
    out=ROOT/'build/beacon.conversion.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    return content(profile_path,report,world+actors)
