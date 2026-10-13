"""Explicit castle gameplay adapter, pinned source functions and mission models.

This deliberately does not label the scoped integer controller as the SM64
engine. Unsupported original behaviors remain visible in the coverage report.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import game_assets
import scene_assets
import sm64_subset

ROOT=Path(__file__).resolve().parents[1]
FUNCTIONS={
    'src/game/behaviors/exclamation_box.inc.c':[
        'exclamation_box_act_0','exclamation_box_act_2','exclamation_box_spawn_contents','exclamation_box_act_4'],
    'src/game/behaviors/sparkle_spawn_star.inc.c':[
        'bhv_spawned_star_init','set_sparkle_spawn_star_hitbox','set_y_home_to_pos','slow_star_rotation','bhv_spawned_star_loop'],
}

def function(text,name):
    text=sm64_subset.clean(text) if hasattr(sm64_subset,'clean') else re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    match=re.search(r'\b(?:void|s32)\s+'+re.escape(name)+r'\([^)]*\)\s*\{',text)
    if not match:raise ValueError('Missing pinned behavior function '+name)
    depth=1;i=match.end()
    while depth and i<len(text):
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    if depth:raise ValueError('Unclosed source function '+name)
    return text[match.start():i]

def import_functions(source):
    rows=[];parts=['// Generated source control flow; integral float literals lowered exactly.']
    for relative,names in FUNCTIONS.items():
        path=source/relative;text=path.read_text()
        for name in names:
            body=function(text,name)
            source_body=body
            # Region and rumble policies are explicit and limited to these
            # pinned functions. Reject unexpected preprocessor branches.
            body=re.sub(r'#if ENABLE_RUMBLE\s*.*?#endif','',body,flags=re.S)
            body=re.sub(r'#ifdef VERSION_JP\s*(.*?)#else\s*(.*?)#endif',lambda m:m[2],body,flags=re.S)
            body=re.sub(r'\s*spawn_triangle_break_particles\(20, MODEL_CARTOON_STAR, 0\.3f, o->oAnimState\);','',body)
            if '#' in body:raise ValueError('Unreviewed behavior preprocessor directive '+name)
            def integral(m):
                value=float(m[0].rstrip('fF'))
                if value!=int(value):raise ValueError('Nonintegral source numeric operation requires a lowering rule: '+name)
                return str(int(value))
            lowered=re.sub(r'\b\d+\.\d+[fF]?\b',integral,body)
            rows.append({'file':relative,'function':name,'source_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'source_body_sha256':hashlib.sha256(source_body.encode()).hexdigest(),
                         'generated_body_sha256':hashlib.sha256(lowered.encode()).hexdigest(),
                         'numeric_lowering':'exact integral literals; integer object positions; no floating arithmetic in these function bodies',
                         'omitted_effects':['rumble','triangle break particles','US region selected']})
            parts.append(lowered)
    (ROOT/'firmware/generated/castle_behaviors.inc').write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
    return rows

def model(source,directory,roots,scale,translation,color):
    path=source/'actors'/directory/'model.inc.c';text=path.read_text()
    textures=set(re.findall(r'gsDPSetTextureImage\([^)]*,\s*(\w+)\s*\)',text))
    textures.update(re.findall(r'gsDPLoadTextureBlock\(\s*(\w+)',text))
    lights=set(re.findall(r'gsSPLight\(\s*&?(\w+)\.',text))
    policy={'discard_state':sorted(sm64_subset.DISCARDABLE_STATE),'opaque_environment':True,
            'flat_texture_block':True,'alpha_as_solid':True,
            'texture_colors':{name:[c/255 for c in color] for name in textures|{'default'}},
            'light_colors':{name:[c/255 for c in color] for name in lights|{'default'}}}
    # Keep source face/material assignments. Flat RGB is an authored fallback,
    # not texture sampling: overlays are darker wood/metal, handles stay gold.
    if directory=='door':
        for name in textures:
            if name.endswith(('0300AD10','0300CD10','0300E510')):
                policy['texture_colors'][name]=[c/255 for c in [max(0,v*2//3) for v in color]]
        policy['light_colors']['door_seg3_lights_03009CF8']=[255/255,208/255,48/255]
    vertices=[];faces=[]
    for root in roots:
        p,t,_,_=sm64_subset.lower(text,{**policy,'display_list':root})
        offset=len(vertices);vertices.extend(p);faces.extend(([i+offset for i in f],m) for f,m in t)
    folder=ROOT/'build/castle-gameplay';folder.mkdir(parents=True,exist_ok=True)
    obj=folder/(directory+'.obj');game_assets.write_obj(obj,vertices,faces,{**policy['texture_colors'],**policy['light_colors']})
    palette,chunks=scene_assets.convert(obj,transform=lambda p:tuple(p[i]*scale+translation[i] for i in range(3)),palette=[tuple(color)])
    if len(chunks)!=1:raise ValueError('Gameplay object model needs one reviewed mesh: '+directory)
    return chunks[0],palette,{'file':path.relative_to(source).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'roots':roots,'source_scale':scale,'geo_translation':translation,'texture_policy':'authored flat RGB per source material; source geometry retained'}


def warp_doors(source,world):
    """Export every source door warp, even when its destination is unsupported.

    Visibility and transition support are separate: rendering a door must not
    silently add a course or enable a warp that the world adapter cannot load.
    """
    from sm64_castle import level_nodes
    nodes={level:level_nodes(source,level) for level in ('castle_grounds','castle_inside','pss')}
    rows=[]
    for area,a in enumerate(world['areas']):
        for o in a['collision']['special_objects']:
            if o['preset'].endswith('_door_warp'):
                kind=2 if 'metal' in o['preset'] else (0 if 'wooden' in o['preset'] else 1)
                rows.append([area,*o['position'],o['yaw'],kind])
        for o in nodes[a['source_level']][a['source_area']]['objects']:
            if o['behavior']=='bhvDoorWarp' and o['model']!='MODEL_NONE':
                kind=2 if 'METAL' in o['model'] else (0 if 'WOODEN' in o['model'] else 1)
                rows.append([area,*o['position'],o['yaw'],kind])
    if len(rows)!=len(set(map(tuple,rows))):raise ValueError('Duplicate source warp-door placement')
    return rows

def generate(source,world,destination):
    preset_names=source/'include/macro_preset_names.h';presets=source/'include/macro_presets.h'
    names=re.search(r'enum MacroPresets\s*\{(.*?)\}',preset_names.read_text(),re.S)[1]
    names=re.sub(r'/\*.*?\*/|//[^\n]*','',names,flags=re.S)
    names=[name.strip() for name in names.split(',') if name.strip()]
    records=[(a,b,value.strip()) for a,b,value in re.findall(r'\{\s*(\w+)\s*,\s*(\w+)\s*,\s*([^{}]+?)\s*\}',presets.read_text())]
    star_box_index=names.index('macro_box_star_1')
    if records[star_box_index]!=('bhvExclamationBox','MODEL_EXCLAMATION_BOX','8'):
        raise ValueError('Original star-box macro preset changed; review its behavior parameter')
    behaviors=source/'data/behavior_data.c'
    script=re.search(r'const BehaviorScript bhvSpawnedStar\[\]\s*=\s*\{(.*?)\};',behaviors.read_text(),re.S)
    if not script or not re.search(r'SET_INT\(oBehParams2ndByte,\s*1\)',script[1]):
        raise ValueError('Review spawned-star behavior-script initialization before porting this source revision')
    functions=import_functions(source)
    movement=[]
    for relative,names in {
        'src/game/mario_actions_moving.c':['update_sliding','update_sliding_angle','update_walking_speed'],
        'src/game/mario_actions_airborne.c':['update_air_without_turn'],
    }.items():
        path=source/relative
        for name in names:
            body=function(path.read_text(),name)
            movement.append({'file':relative,'function':name,'source_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'source_body_sha256':hashlib.sha256(body.encode()).hexdigest(),'implementation':'reviewed integer lowering, not verbatim C'})
    moving=(source/'src/game/mario_actions_moving.c').read_text()
    airborne=(source/'src/game/mario_actions_airborne.c').read_text()
    if '1.1f - m->forwardVel / 43.0f' not in moving or '0.35f, 0.35f' not in airborne:
        raise ValueError('Review original movement coefficients before lowering this source revision')
    specs=[('box','exclamation_box',['exclamation_box_seg8_dl_08019438'],2,[0,0,0],[240,184,32]),
           ('star','star',['star_seg3_dl_0302B870'],0.25,[0,0,0],[255,224,40]),
           ('door','door',['door_seg3_dl_03014A80'],0.25,[3,0,0],[132,76,32]),
           ('castle_door','door',['door_seg3_dl_03013E28'],0.25,[3,0,0],[216,182,124]),
           ('metal_door','door',['door_seg3_dl_03014BE0'],0.25,[3,0,0],[112,128,144]),
           ('coin','coin',['coin_seg3_dl_03007800'],1,[0,0,0],[255,224,40])]
    lines=['#ifndef CASTLE_GAMEPLAY_DATA_H','#define CASTLE_GAMEPLAY_DATA_H','#include "assets.h"','#include "game_services.h"',
           '#define CASTLE_GAMEPLAY_STORAGE __attribute__((section(".game_assets")))']
    models=[];palette=world['resident_scene']['palette']
    for name,directory,roots,scale,translation,color in specs:
        (vertices,triangles),mesh_palette,report=model(source,directory,roots,scale,translation,color)
        if directory!='door':mesh_palette=[tuple(color)]
        remap=[]
        for rgb in mesh_palette:
            rgb=list(rgb)
            if rgb not in palette:
                if len(palette)>=256:raise ValueError('Gameplay palette exceeds 256 colors')
                palette.append(rgb)
            remap.append(palette.index(rgb))
        index=palette.index(color)
        triangle_colors=[remap[t[3]] if directory=='door' else index for t in triangles]
        lines+=['static const CASTLE_GAMEPLAY_STORAGE scene_vertex_t castle_'+name+'_vertices[]={'+','.join('{'+','.join(map(str,v))+'}' for v in vertices)+'};',
                'static const CASTLE_GAMEPLAY_STORAGE scene_triangle_t castle_'+name+'_triangles[]={'+','.join('{'+','.join(map(str,t[:3]))+','+str(c)+'}' for t,c in zip(triangles,triangle_colors))+'};',
                'static const CASTLE_GAMEPLAY_STORAGE scene_mesh_t castle_'+name+'_mesh={castle_'+name+'_vertices,castle_'+name+'_triangles,'+str(len(vertices))+','+str(len(triangles))+'};']
        report.update({'id':name,'vertices':len(vertices),'triangles':len(triangles),'palette_index':index,
                       'used_palette_indices':sorted(set(triangle_colors))});models.append(report)
        if name=='star':lines.append('#define CASTLE_HUD_COLOR '+str(index)+'u')
    macros=source/'levels/pss/areas/1/macro.inc.c';coins=[];boxes=[]
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',macros.read_text(),flags=re.S)
    for command,args in sm64_subset.calls(text[text.index('{')+1:text.rindex('}')],r'[A-Z_][A-Z_0-9]*'):
        if command=='MACRO_OBJECT' and args[0]=='macro_box_star_1':boxes.append([int(x) for x in args[2:5]])
        if command=='MACRO_OBJECT' and args[0]=='macro_yellow_coin_2':coins.append([int(x) for x in args[2:5]])
    if len(boxes)!=1:raise ValueError('Secret Slide requires exactly one original star box')
    lines.append('static const CASTLE_GAMEPLAY_STORAGE int16_t castle_box_position[3]={'+','.join(map(str,boxes[0]))+'};')
    collision_path=source/'actors/exclamation_box_outline/collision.inc.c'
    points=[[int(v.strip())*2 for v in args.split(',')] for args in re.findall(r'COL_VERTEX\(([^)]*)\)',collision_path.read_text())]
    if len(points)!=8:raise ValueError('Review dynamic box collision lowering for this source revision')
    bounds=[n for axis in range(3) for n in (min(p[axis] for p in points),max(p[axis] for p in points))]
    if set(map(tuple,points))!={(x,y,z) for x in bounds[:2] for y in bounds[2:4] for z in bounds[4:6]}:
        raise ValueError('Dynamic box collider must remain an axis-aligned source cube')
    lines.append('static const CASTLE_GAMEPLAY_STORAGE game_bounds_t castle_box_bounds={'+','.join(map(str,bounds))+'};')
    doors=[]
    for area,a in enumerate(world['areas']):
        for o in a['collision']['special_objects']:
            if o['preset']=='special_wooden_door' or re.fullmatch(r'special_[013]stars?_door',o['preset']):
                requirement=int(re.search(r'\d+',o['preset'])[0]) if re.search(r'\d+',o['preset']) else 0
                doors.append([area,*o['position'],o['yaw'],requirement,0 if o['preset']=='special_wooden_door' else 1])
    lines.append('static const CASTLE_GAMEPLAY_STORAGE int16_t castle_local_doors[][7]={'+','.join('{'+','.join(map(str,d))+'}' for d in doors)+'};')
    lines.append('#define CASTLE_LOCAL_DOOR_COUNT '+str(len(doors))+'u')
    warps=warp_doors(source,world)
    lines.append('static const CASTLE_GAMEPLAY_STORAGE int16_t castle_warp_doors[][6]={'+','.join('{'+','.join(map(str,d))+'}' for d in warps)+'};')
    lines.append('#define CASTLE_WARP_DOOR_COUNT '+str(len(warps))+'u')
    lines.append('static const CASTLE_GAMEPLAY_STORAGE int16_t castle_slide_coins[][3]={'+','.join('{'+','.join(map(str,p))+'}' for p in coins)+'};')
    lines.append('#define CASTLE_SLIDE_COIN_COUNT '+str(len(coins))+'u')
    lines.append('static const CASTLE_GAMEPLAY_STORAGE int16_t castle_game_rotations[256][2]={'+','.join('{%d,%d}'%(round(math.cos(i*math.tau/256)*256),round(math.sin(i*math.tau/256)*256)) for i in range(256))+'};')
    lines.append('#endif')
    (ROOT/'firmware/generated/castle_gameplay_data.h').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Inventory every level-script behavior, including those not yet ported.
    inventory=[]
    for level in ('castle_grounds','castle_inside','pss'):
        path=source/'levels'/level/'script.c'
        for behavior in sorted(set(re.findall(r'\b(bhv\w+)\b',path.read_text()))):
            inventory.append({'level':level,'behavior':behavior,'status':'transition-adapter' if 'Warp' in behavior or behavior=='bhvWarp' else 'not-original-engine-ported'})
    report={'format':'soc-sm64-gameplay-coverage','version':1,'source_commit':json.loads((ROOT/'sm64.lock.json').read_text())['commit'],
            'imported_functions':functions,'models':models,'local_doors':len(doors),'warp_doors':warps,'slide_single_coins':len(coins),
            'movement_sources':movement,
            'numeric_policy':{'velocities':'Q8; nearest source coefficient, integer division truncates toward zero',
                'trig':'256-angle Q8 sine/cosine; Mario display yaw retains existing 32 directions',
                'derived_coefficients':{'walking_1_1':round(1.1*256),'air_drag_0_35':round(0.35*256),
                    'friction_0_98':round(0.98*256),'friction_0_96':round(0.96*256),'friction_0_92':round(0.92*256),
                    'steering_0_02':round(0.02*256),'slide_1_degree_normal_y':round(0.9998477*4096)},
                'authored_safety':'100 source units/tick vector cap; horizontal collision substeps at most 8 units and radius/2, rebinding the spatial grid every substep'},
            'save_fixture':{'initial_stars':70,'initial_key_bits':3,'slide_star_bit':0,'reason':'unlocked castle traversal fixture, not original new-game progression'},
            'mission_source':{'file':macros.relative_to(source).as_posix(),'sha256':hashlib.sha256(macros.read_bytes()).hexdigest(),'box_position':boxes[0]},
            'behavior_script':{'file':'data/behavior_data.c','sha256':hashlib.sha256(behaviors.read_bytes()).hexdigest(),
                'spawned_star_second_byte':1,'spawned_star_set_home':True},
            'macro_preset':{'name':'macro_box_star_1','index':star_box_index,'contents':8,
                'sources':[{'file':p.relative_to(source).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (preset_names,presets)]},
            'box_collision':{'file':collision_path.relative_to(source).as_posix(),'sha256':hashlib.sha256(collision_path.read_bytes()).hexdigest(),
                'scale':2,'bounds':bounds,'runtime':'shared axis-aligned solid collider; original triangle solver not ported'},
            'supported':'five original areas and transitions; source box/star control flow; scoped fixed-point walking/sliding, attack, ground pound; RAM mission save',
            'limitations':['not complete SM64 action engine','shared capsule collision instead of original mario_step.c','quantized movement and trigonometry',
                'wooden/castle door source geometry retained; star-number alpha badges deferred; authored hinge interaction',
                'source star-spawn timing retained but camera cutscene adapted to gameplay freeze','audio, particles, dialog, swimming, original Lakitu, NPCs, caps and other missions not ported',
                'coin billboard geometry retained with solid flat color; alpha textures and coin-line/blue-coin spawning not implemented','save persists area changes and retries, not power cycles'],
            'behavior_inventory':inventory}
    (destination/'gameplay-coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    world['gameplay']=report
    world['implementation_status']='scoped castle gameplay; original engine incomplete'
    return report
