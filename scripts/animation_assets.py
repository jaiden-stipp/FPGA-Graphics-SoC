"""Read original SM64 GeoLayout joints and indexed animation channels.

Only declared switch branches and neutral callbacks are accepted. Source files
are read-only. Channel interning is lossless over every reachable source frame.
"""
import hashlib
import math
from pathlib import Path
import re
import sm64_subset

def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)

def number(value):
    value=value.strip()
    if not re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|[0-9]+)',value):
        raise ValueError('Expected an animation integer literal: '+value)
    return int(value,0) if 'x' in value.lower() else int(value)

def source_path(source,name):
    p=(source/name).resolve()
    if not p.is_relative_to(source.resolve()):raise ValueError('Animation source escapes pinned checkout')
    return p

def hierarchy(source,policy):
    p=source_path(source,policy['geo_source']);text=p.read_text()
    arrays=dict(re.findall(r'const\s+GeoLayout\s+(\w+)\s*\[\]\s*=\s*\{(.*?)\};',clean(text),re.S))
    joints=[];display={};active=[];discarded=set();omitted=set();choices=policy['switch_choices']
    def tree(name):
        if name not in arrays:raise ValueError('Unresolved GeoLayout: '+name)
        root={'children':[]};stack=[root]
        for command,args in sm64_subset.calls(arrays[name].replace('GEO_','gsGEO_')):
            command=command[2:]
            if command=='GEO_OPEN_NODE':
                if not stack[-1]['children']:raise ValueError('GeoLayout opens missing node')
                stack.append(stack[-1]['children'][-1])
            elif command=='GEO_CLOSE_NODE':
                if len(stack)==1:raise ValueError('GeoLayout closes root')
                stack.pop()
            elif command=='GEO_RETURN':continue
            else:stack[-1]['children'].append({'command':command,'args':args,'children':[]})
        if len(stack)!=1:raise ValueError('Unbalanced GeoLayout')
        return root['children']
    def walk(nodes,parent):
        for node in nodes:
            cmd,args=node['command'],node['args'];current=parent
            if cmd=='GEO_TRANSLATE_ROTATE':
                def descendants(n):
                    yield n
                    for child in n['children']:yield from descendants(child)
                subtree=list(descendants(node))
                lists=[n['args'] for n in subtree if n['command']=='GEO_DISPLAY_LIST']
                if any(n['command']=='GEO_ANIMATED_PART' for n in subtree) or not lists or any(
                    layer!='LAYER_ALPHA' or name not in policy.get('omit_static_alpha',[]) for layer,name in lists):
                    raise ValueError('Static transformed branch needs an explicit alpha omission policy')
                omitted.update(name for _,name in lists);continue
            if cmd=='GEO_BRANCH':
                name=args[1]
                if name in active:raise ValueError('Cyclic GeoLayout')
                active.append(name);walk(tree(name),parent);active.pop()
            elif cmd=='GEO_ANIMATED_PART':
                if args[0]!='LAYER_OPAQUE':raise ValueError('Animated layer has no opaque policy')
                current=len(joints);joints.append({'parent':parent,'translation':[number(v) for v in args[1:4]]})
                if args[4]!='NULL':
                    if args[4] in display:raise ValueError('Repeated animated display list')
                    display[args[4]]=current
            elif cmd=='GEO_DISPLAY_LIST':
                if args[0]!='LAYER_OPAQUE' or parent<0:raise ValueError('Unbound/nonopaque animated display list')
                if args[1] in display:raise ValueError('Repeated animated display list')
                display[args[1]]=parent
            elif cmd=='GEO_SWITCH_CASE':
                callback=args[1]
                if callback not in choices:raise ValueError('Declare GeoLayout switch: '+callback)
                selection=choices[callback]
                if not isinstance(selection,int) or not 0<=selection<len(node['children']):
                    raise ValueError('GeoLayout switch index outside children')
                walk([node['children'][selection]],parent);continue
            elif cmd=='GEO_ASM':
                if args[1] not in policy['neutral_callbacks']:raise ValueError('Unsupported dynamic GeoLayout callback: '+args[1])
                discarded.add(args[1])
            elif cmd=='GEO_ROTATION_NODE':
                if any(number(a)!=0 for a in args[1:]):raise ValueError('Static rotation requires a lowering rule')
            elif cmd=='GEO_SCALE':
                if number(args[1])!=65536:raise ValueError('Nonunit GeoLayout scale requires a lowering rule')
            elif cmd=='GEO_HELD_OBJECT':
                if args[-1] not in policy.get('omit_held_objects',[]) or node['children']:
                    raise ValueError('Held object requires an explicit omission policy')
                discarded.add(args[-1])
            else:raise ValueError('Unsupported skeletal GeoLayout node: '+cmd)
            walk(node['children'],current)
    active.append(policy['geo_root']);walk(tree(policy['geo_root']),-1)
    if not 1<=len(joints)<=32:raise ValueError('Skeleton needs 1..32 parent-ordered joints')
    return joints,display,{'source':policy['geo_source'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'root':policy['geo_root'],'switch_choices':choices,'neutral_callbacks':sorted(discarded),
        'omitted_static_alpha':sorted(omitted)}

def clip(source,spec,joint_count):
    p=source_path(source,spec['source']);text=clean(p.read_text());name=spec['symbol']
    match=re.search(r'struct\s+Animation\s+'+re.escape(name)+r'\s*\[\]\s*=\s*\{(.*?)\};',text,re.S)
    if not match:raise ValueError('Missing original animation '+name)
    fields=[v.strip() for v in match[1].strip().strip(',').split(',')]
    if len(fields)!=9:raise ValueError('Unsupported animation descriptor')
    flags,divisor,start,loop,end=map(number,fields[:5])
    if flags & ~1 or divisor!=189 or not 0<=loop<=start<end<=256:
        raise ValueError('Unsupported animation flags/frame/translation convention')
    values_name,indices_name=fields[6:8]
    if fields[5]!='ANIMINDEX_NUMPARTS('+indices_name+')' or number(fields[8])!=0:
        raise ValueError('Unsupported original animation descriptor references')
    def array(symbol,typ):
        m=re.search(r'const\s+'+typ+r'\s+'+re.escape(symbol)+r'\s*\[\]\s*=\s*\{(.*?)\};',text,re.S)
        if not m:raise ValueError('Missing animation array '+symbol)
        return [number(v) for v in m[1].strip().strip(',').split(',')]
    values=[(v+32768)%65536-32768 for v in array(values_name,'s16')]
    indices=array(indices_name,'u16')
    if len(indices)!=6*(joint_count+1):raise ValueError('Clip channel count differs from source skeleton')
    channels=[]
    for count,index in zip(indices[::2],indices[1::2]):
        if count<1 or index+count>len(values):raise ValueError('Animation channel outside values')
        samples=[values[index+min(frame,count-1)] for frame in range(start,end)]
        while len(samples)>1 and samples[-1]==samples[-2]:samples.pop()
        channels.append(samples)
    return {'role':spec['role'],'symbol':name,'flags':flags,'start':start,'loop':loop,'end':end,
        'channels':channels,'source':spec['source'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'source_values':len(values),'source_indices':indices,'raw_values':values,'divisor':divisor}

def rotation(angles):
    # Original sins/coss use unsigned 16-bit angles with their low four bits
    # discarded. This independent floating reference follows that convention.
    sx,sy,sz=[math.sin(((a&65535)>>4)*math.tau/4096) for a in angles]
    cx,cy,cz=[math.cos(((a&65535)>>4)*math.tau/4096) for a in angles]
    return [[cy*cz,sx*sy*cz-cx*sz,cx*sy*cz+sx*sz],
            [cy*sz,sx*sy*sz+cx*cz,cx*sy*sz-sx*cz],[-sy,sx*cy,cx*cy]]

def pose(joints,clip,frame):
    frame=max(clip['start'],min(frame,clip['end']-1));offset=frame-clip['start']
    values=[ch[min(offset,len(ch)-1)] for ch in clip['channels']];matrices=[]
    for i,joint in enumerate(joints):
        r=rotation(values[3+3*i:6+3*i]);t=joint['translation'][:]
        if i==0:t[1]+=values[1] # Preserve vertical bob; lateral root motion belongs to the controller.
        parent=joint['parent']
        if parent>=0:
            pr,pt=matrices[parent]
            t=[sum(pr[a][b]*t[b] for b in range(3))+pt[a] for a in range(3)]
            r=[[sum(pr[a][k]*r[k][b] for k in range(3)) for b in range(3)] for a in range(3)]
        matrices.append((r,t))
    return matrices

def vertex(matrix,point):
    r,t=matrix
    return tuple(sum(r[a][b]*point[b] for b in range(3))+t[a] for a in range(3))

def load(source,policy):
    joints,display,provenance=hierarchy(source,policy)
    clips=[clip(source,spec,len(joints)) for spec in policy['clips']]
    if [c['role'] for c in clips]!=['idle','walk','jump','land']:
        raise ValueError('Declare idle/walk/jump/land animation roles in order')
    return joints,display,clips,provenance

def prepare(source,policy,parts,local_points,faces,chunks):
    joints,display,clips,provenance=load(source,policy)
    bones=[]
    for part,points in parts:
        if part['display_list'] not in display:raise ValueError('Actor part missing from selected original GeoLayout')
        bones += [display[part['display_list']]]*len(points)
    if set(display)!={part['display_list'] for part,_ in parts}:
        raise ValueError('Selected GeoLayout and actor parts differ')
    bind=pose(joints,clips[0],clips[0]['start'])
    posed=[vertex(bind[b],p) for b,p in zip(bones,local_points)]
    low=min(p[1] for p in posed);high=max(p[1] for p in posed)
    scale=round(policy['height']*16384/(high-low));base_y=round(low*16)
    rate=policy['walk_rate_q8']
    if not 256<=scale<=16384 or not isinstance(rate,int) or not 1<=rate<=2048:
        raise ValueError('Animation scale/rate exceeds fixed-point bounds')
    packed=[];local={};ids=[];count=0
    for face,_ in faces:
        face=[i-1 for i in face]
        if count==256 or len(local)+len(set(face)-local.keys())>128:
            packed.append(ids);local={};ids=[];count=0
        for i in face:
            if i not in local:local[i]=len(ids);ids.append(i)
        expected=tuple(local[i] for i in face)
        if chunks[len(packed)][1][count][:3]!=expected:
            raise ValueError('Animation packing differs from static source triangle connectivity')
        count+=1
    packed.append(ids)
    if [len(p) for p in packed]!=[len(v) for v,_ in chunks]:raise ValueError('Animation packing changed vertex counts')
    new_chunks=[([local_points[i] for i in indices],triangles) for indices,(_,triangles) in zip(packed,chunks)]
    vertex_bones=[bones[i] for indices in packed for i in indices]
    foot_names=policy['ground_parts']
    if not foot_names or set(foot_names)-set(display):raise ValueError('Declare grounded contact parts from selected geometry')
    foot_mask=sum(1<<display[n] for n in set(foot_names))
    values=[];intern={};descriptors=[]
    for c in clips:
        channels=[]
        for samples in c['channels']:
            key=tuple(samples)
            if key not in intern:intern[key]=len(values);values.extend(samples)
            channels.append((len(samples),intern[key]))
        descriptors.append(channels)
    if len(values)>32767:raise ValueError('Animation values exceed the indexed data budget')
    lines=['#define GAME_HAS_ANIMATION 1','#include "animation.h"',f'#define GAME_ANIMATION_VERTICES {len(vertex_bones)}u',
           f'#define GAME_ANIMATION_JOINTS {len(joints)}u',
           'static const animation_joint_t game_animation_joints[]={']
    lines += ['{'+','.join(map(str,[j['parent'],*j['translation']]))+'},' for j in joints]
    lines += ['};','static const int16_t game_animation_values[]={'+','.join(map(str,values))+'};',
              'static const int16_t game_animation_sines[]={'+','.join(str(round(math.sin(i*math.pi/2048)*16384)) for i in range(1025))+'};',
              'static const uint8_t game_animation_vertex_joints[]={'+','.join(map(str,vertex_bones))+'};']
    for i,channels in enumerate(descriptors):
        lines += [f'static const animation_channel_t game_animation_channels_{i}[]={{'+
                  ','.join('{'+','.join(map(str,v))+'}' for v in channels)+'};']
    lines += ['static const animation_clip_t game_animation_clips[]={']
    lines += [f'{{game_animation_channels_{i},{c["flags"]},{c["start"]},{c["end"]},{c["loop"]}}},' for i,c in enumerate(clips)]
    lines += ['};','static const animation_package_t game_animation_package={game_animation_joints,'+
              'game_animation_clips,game_animation_values,game_animation_sines,actor_meshes,'+
              'game_animation_vertex_joints,'+','.join(map(str,[len(joints),len(chunks),len(vertex_bones),scale,base_y,rate,foot_mask]))+'};']
    report={'hierarchy':provenance,'joints':joints,'display_joints':display,'vertex_joints':vertex_bones,
        'vertex_sources':[{'joint':bones[i],'local':local_points[i],'source_index':i} for ids in packed for i in ids],
        'scale_q14':scale,'base_y_q4':base_y,'walk_rate_q8':rate,'foot_joints':foot_mask,
        'unique_samples':len(values),'samples_bytes':2*len(values),'root_motion':'original vertical channel; lateral channels not applied; grounded soles use a common render offset',
        'palette':'unchanged declared standing-pose flat lighting; animated normals not relit',
        'clips':[{k:c[k] for k in ('role','symbol','flags','start','loop','end','source','sha256','source_values')} for c in clips]}
    return new_chunks,lines,report
