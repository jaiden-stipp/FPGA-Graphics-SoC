"""Bounded Quake PACK/BSP29 adapter; original world faces to the shared SoC ABI.

Format reference: id-Software/Quake, WinQuake/bspfile.h and gl_rsurf.c.
Game data stays external. Never execute the shareware installer.
"""
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import urllib.error
import urllib.request
import zipfile
import game_assets
import game_package

ROOT=Path(__file__).resolve().parents[1]
SHAREWARE_URL='https://www.gamers.org/pub/idgames/idstuff/quake/quake106.zip'
SHAREWARE_MIRROR='https://ftp.gwdg.de/pub/misc/ftp.idsoftware.com/idstuff/quake/quake106.zip'
ZIP_SHA='ec6c9d34b1ae0252ac0066045b6611a7919c2a0d78a3a66d9387a8f597553239'
PAK_SHA='35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af'

def digest(data): return hashlib.sha256(data).hexdigest()

def fetch_shareware():
    directory=ROOT/'build/quake-shareware'; directory.mkdir(parents=True,exist_ok=True)
    pak=directory/'pak0.pak'
    if pak.exists() and digest(pak.read_bytes())==PAK_SHA: return pak
    archive=directory/'quake106.zip'
    if not archive.exists():
        failures=[]
        for url in (SHAREWARE_URL,SHAREWARE_MIRROR):
            try:
                with urllib.request.urlopen(url,timeout=30) as response:
                    data=response.read(10*1024*1024)
                break
            except (urllib.error.URLError,TimeoutError) as error:
                failures.append(str(error))
        else:raise RuntimeError('Quake shareware download failed: '+'; '.join(failures))
        if digest(data)!=ZIP_SHA: raise ValueError('Quake shareware archive hash mismatch')
        archive.write_bytes(data)
    if digest(archive.read_bytes())!=ZIP_SHA: raise ValueError('Quake shareware archive hash mismatch')
    with zipfile.ZipFile(archive) as z:
        resource=z.read('resource.1')
    resource_path=directory/'resource.1'; resource_path.write_bytes(resource)
    tar=shutil.which('bsdtar') or (shutil.which('tar') if __import__('os').name=='nt' else None)
    if not tar: raise ValueError('Shareware extraction requires bsdtar (libarchive-tools), or Windows tar.exe')
    # Extract only data/license files to explicit paths; never run DOS programs.
    for member,name in (('ID1/PAK0.PAK','pak0.pak'),('LICINFO.TXT','LICINFO.TXT'),('README.TXT','README.TXT')):
        with (directory/name).open('wb') as out:
            subprocess.run([tar,'-xOf',str(resource_path),member],stdout=out,check=True)
    if digest(pak.read_bytes())!=PAK_SHA: raise ValueError('Quake shareware PAK hash mismatch')
    return pak

def pak_entries(data):
    if len(data)<12: raise ValueError('Truncated PACK header')
    magic,offset,length=struct.unpack_from('<4sii',data)
    if magic!=b'PACK' or offset<12 or length<0 or length%64 or offset+length>len(data):
        raise ValueError('Invalid PACK directory')
    result={}
    for index in range(offset,offset+length,64):
        name,start,size=struct.unpack_from('<56sii',data,index)
        name=name.split(b'\0')[0].decode('ascii')
        if start<12 or size<0 or start+size>len(data) or name in result: raise ValueError('Invalid PACK entry')
        result[name]=data[start:start+size]
    return result

def bsp_lumps(data):
    if len(data)<124 or struct.unpack_from('<i',data)[0]!=29: raise ValueError('Expected Quake BSP version 29')
    result=[]
    for index in range(15):
        offset,length=struct.unpack_from('<ii',data,4+index*8)
        if offset<0 or length<0 or offset+length>len(data): raise ValueError('BSP lump outside file')
        result.append(data[offset:offset+length])
    return result

def records(data,fmt):
    if len(data)%struct.calcsize(fmt): raise ValueError('Partial BSP record')
    return list(struct.iter_unpack(fmt,data))

def prepare(pak_path,profile):
    entries=pak_entries(pak_path.read_bytes())
    raw=entries[profile['map']]
    if digest(raw)!=profile['map_sha256']: raise ValueError('Map hash differs from selected profile')
    lumps=bsp_lumps(raw)
    entities=[dict(re.findall(r'"([^"]*)"\s*"([^"]*)"',item)) for item in re.findall(r'\{([^}]*)\}',lumps[0].decode('ascii'))]
    start=next(e for e in entities if e.get('classname')=='info_player_start')
    origin=list(map(float,start['origin'].split())); scale=game_package.integer(profile['scale'],1,4)
    radius=game_package.integer(profile['selection_radius'],128,1024)
    origin[2]-=24 # Original Quake standing hull minimum; GPU player position is feet.
    vertices=records(lumps[3],'<3f'); planes=records(lumps[1],'<4fi')
    if any(not all(math.isfinite(v) for v in point) for point in vertices): raise ValueError('Non-finite source vertex')
    edges=records(lumps[12],'<2H'); surfedges=[row[0] for row in records(lumps[13],'<i')]
    faces=records(lumps[7],'<hhihh4Bi'); texinfo=records(lumps[6],'<8fii'); models=records(lumps[14],'<9f7i')
    if not models: raise ValueError('Missing world model')
    first,count=models[0][-2:]
    if first<0 or count<0 or first+count>len(faces): raise ValueError('Invalid world face range')
    source_palette=records(entries['gfx/palette.lmp'],'<3B')
    if len(source_palette)!=256: raise ValueError('Quake palette must contain 256 colors')
    palette=[tuple(profile['appearance']['background'])]+source_palette[1:]
    for channel in palette[0]:game_package.integer(channel,0,255)
    texture_data=lumps[2]
    if len(texture_data)<4: raise ValueError('Missing BSP textures')
    texture_count=struct.unpack_from('<i',texture_data)[0]
    if not 0<texture_count<=512 or 4+texture_count*4>len(texture_data): raise ValueError('Invalid BSP texture directory')
    textures=[]
    for offset in struct.unpack_from('<'+str(texture_count)+'i',texture_data,4):
        if offset<0: textures.append(('missing',(128,128,128))); continue
        if offset+40>len(texture_data): raise ValueError('Truncated miptex')
        name,width,height,*mips=struct.unpack_from('<16s6I',texture_data,offset)
        if not width or not height or width>1024 or height>1024 or mips[0]<40 or offset+mips[0]+width*height>len(texture_data):
            raise ValueError('Invalid miptex pixels')
        histogram=Counter(texture_data[offset+mips[0]:offset+mips[0]+width*height])
        rgb=tuple(round(sum(source_palette[i][channel]*n for i,n in histogram.items())/(width*height)) for channel in range(3))
        textures.append((name.split(b'\0')[0].decode('ascii'),rgb))
    points=[tuple(round((point[axis]-origin[axis])*scale) for axis in (0,2,1)) for point in vertices]
    chunks=[]; local={}; packed=[]; triangles=[]; mapping=[]; face_ids=[]; source_triangles=[]; omitted=Counter(); flipped=0
    def flush():
        nonlocal local,packed,triangles,mapping
        if triangles:chunks.append((packed,triangles)); source_triangles.append(mapping)
        local={}; packed=[]; triangles=[]; mapping=[]
    for face_id in range(first,first+count):
        plane,side,edge_start,edge_count,info,*rest=faces[face_id]
        if not 0<=plane<len(planes) or not 0<=info<len(texinfo) or edge_count<3 or edge_start<0 or edge_start+edge_count>len(surfedges):
            raise ValueError('Invalid source face')
        polygon=[]
        for edge_id in surfedges[edge_start:edge_start+edge_count]:
            if abs(edge_id)>=len(edges): raise ValueError('Invalid surfedge')
            vertex_id=edges[abs(edge_id)][0 if edge_id>=0 else 1]
            if vertex_id>=len(vertices): raise ValueError('Invalid source vertex index')
            polygon.append(vertex_id)
        original=[vertices[i] for i in polygon]
        if any(max(v[a] for v in original)<origin[a]-radius or min(v[a] for v in original)>origin[a]+radius for a in (0,1)):
            omitted['outside_selection']+=1;continue
        ti=texinfo[info];texture_id=ti[8]
        if not 0<=texture_id<len(textures):raise ValueError('Invalid miptex index')
        name,rgb=textures[texture_id]
        if any(name.startswith(prefix) for prefix in profile['appearance']['skip_textures']):
            omitted['unsupported_material']+=1;continue
        light=128
        light_offset=rest[-1]
        if light_offset>=0 and not(ti[9]&1):
            dimensions=[]
            for axis in (0,4):
                uv=[sum(v[i]*ti[axis+i] for i in range(3))+ti[axis+3] for v in original]
                dimensions.append(math.ceil(max(uv)/16)-math.floor(min(uv)/16)+1)
            samples=dimensions[0]*dimensions[1]
            if samples<=0 or light_offset+samples>len(lumps[8]):raise ValueError('Invalid face lightmap')
            light=sum(lumps[8][light_offset:light_offset+samples])/samples
        color=tuple(min(255,round(channel*light/128)) for channel in rgb)
        color_index=min(range(1,256),key=lambda i:sum((palette[i][a]-color[a])**2 for a in range(3)))
        normal=planes[plane][:3];normal=tuple(n*(-1 if side else 1) for n in normal)
        target_normal=(normal[0],normal[2],normal[1])
        face_ids.append(face_id)
        for index in range(1,len(polygon)-1):
            ids=[polygon[0],polygon[index],polygon[index+1]]; pts=[points[i] for i in ids]
            u=[pts[1][i]-pts[0][i] for i in range(3)];v=[pts[2][i]-pts[0][i] for i in range(3)]
            cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            if not any(cross):omitted['zero_area_fan_triangles']+=1;continue
            if sum(cross[i]*target_normal[i] for i in range(3))<0:ids[1],ids[2]=ids[2],ids[1];flipped+=1
            if any(any(abs(c)>8192 for c in points[i]) for i in ids):raise ValueError('Selected geometry exceeds Q8.8 adapter range')
            if len(local)+sum(i not in local for i in ids)>128 or len(triangles)==256:flush()
            for i in ids:
                if i not in local:local[i]=len(packed);packed.append(points[i])
            triangles.append(tuple(local[i] for i in ids)+(color_index,));mapping.append({'face':face_id,'vertices':ids,'color':color_index})
    flush()
    if not chunks or len(chunks)>16:raise ValueError('Selected Quake region exceeds GPU mesh capacity')
    floors,walls=game_assets.collision(chunks)
    floor=game_assets.floor_height(floors,0,0,48)
    if floor==-32768:raise ValueError('Original start has no displayed floor')
    spawn=[0,floor,0]
    yaw=round((90-float(start.get('angle','0')))%360*64/360)&63
    report={'module':'quake','profile':profile['name'],'map':profile['map'],'pak_sha256':digest(pak_path.read_bytes()),
            'map_sha256':digest(raw),'palette_colors':256,'meshes':len(chunks),'world_triangles':sum(len(t) for _,t in chunks),
            'actor_triangles':0,'collision_floors':len(floors),'collision_walls':len(walls),'spawn_q8_8':spawn,
            'physics':profile['physics'],'camera':profile['camera'],'source_origin':origin,'scale':scale,'source_spawn_entity':start,
            'initial_yaw':yaw,'selected_face_ids':face_ids,'chunk_source_triangles':source_triangles,
            'source_world_faces':count,'source_world_fan_triangles':sum(f[3]-2 for f in faces[first:first+count]),
            'omissions':dict(omitted),'platform_winding_reversals':flipped,
            'axis_policy':'source [x,y,z] -> GPU [x,z,y]; orient fan winding to transformed original plane normals',
            'appearance_policy':'nearest original palette color to texture RGB mean times first lightmap style mean; no runtime textures',
            'original_engine_ported':False,'original_entities_ported':False}
    return chunks,palette,floors,walls,report

def generate(profile_path,pak_path):
    profile=json.loads(profile_path.read_text())
    if profile.get('module')!='quake':raise ValueError('Expected Quake scene profile')
    chunks,palette,floors,walls,report=prepare(pak_path,profile)
    physics=profile['physics']; order=('speed','radius','height','step_height','gravity','jump_speed','kill_y')
    for key in order:game_package.integer(physics[key],-8192,256)
    if not 0<physics['speed']<=physics['radius']//2 or not 0<physics['gravity']<=16 or physics['height']<32:
        raise ValueError('Invalid bounded scene physics')
    camera=profile['camera']; game_package.integer(camera['focal'],128,512)
    # The unchanged GPU emits low eight bits of floor(65536 / camera_z).
    # z >= 257 keeps every projected/clipped depth in the representable range.
    game_package.integer(camera['near_z'],257,1024)
    game_package.integer(camera['eye_height'],1,physics['height'])
    lines=['// Original Quake BSP29 face geometry, explicit platform/appearance adapters.','#ifndef QUAKE_DATA_H','#define QUAKE_DATA_H',
        '#include "assets.h"','#include "first_person.h"','#ifdef GAME_USE_SDRAM',
        '#define GAME_STORAGE __attribute__((section(".game_assets")))','#else','#define GAME_STORAGE','#endif',
        f'#define GAME_WORLD_MESHES {len(chunks)}u',f'#define GAME_PALETTE_COUNT {len(palette)}u',
        f'#define GAME_FOCAL {camera["focal"]}',f'#define GAME_NEAR_Z {camera["near_z"]}',
        'static const uint8_t game_palette[][3]={'+','.join('{'+','.join(map(str,c))+'}' for c in palette)+'};']
    for i,(vertices,triangles) in enumerate(chunks):
        for name,values,typ in (('vertices',vertices,'scene_vertex_t'),('triangles',triangles,'scene_triangle_t')):
            lines.append(f'static const {typ} world_{name}_{i}[]={{'+','.join('{'+','.join(map(str,v))+'}' for v in values)+'};')
    lines.append('static const scene_mesh_t world_meshes[]={'+','.join(f'{{world_vertices_{i},world_triangles_{i},{len(v)},{len(t)}}}' for i,(v,t) in enumerate(chunks))+'};')
    for name,data,typ in (('floors',floors,'collision_floor_t'),('walls',walls,'collision_wall_t')):
        rows=['{'+','.join('{'+','.join(map(str,p))+'}' for p in pts)+','+','.join(map(str,rest))+'}' for pts,rest in data]
        lines.append(f'static const {typ} game_{name}[]={{'+','.join(rows or ['{0}'])+'};')
    lines.append('static const player_world_t game_world={game_floors,game_walls,'+','.join(map(str,[len(floors),len(walls)]+report['spawn_q8_8']+[physics[k] for k in order]))+'};')
    rotations=[[round(math.cos(i*math.tau/64)*256),round(math.sin(i*math.tau/64)*256)] for i in range(64)]
    lines.append('static const int16_t game_rotations[][2]={'+','.join('{'+','.join(map(str,p))+'}' for p in rotations)+'};')
    lines.append('static const first_person_config_t game_first_person={game_rotations,'+','.join(map(str,[report['initial_yaw'],camera['eye_height'],profile['selection_radius']*profile['scale']]))+'};')
    lines+=['#endif','']
    (ROOT/'firmware/generated/quake_data.h').write_text('\n'.join(lines).replace('static const ','static const GAME_STORAGE '))
    (ROOT/'build/quake.conversion.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Quake E1M1 start region: {report["world_triangles"]} triangles, {len(chunks)} handles, spawn {report["spawn_q8_8"]}')
    return game_package.content(profile_path,report,chunks)
