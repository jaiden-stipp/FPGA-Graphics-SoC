"""Exercise source-independent worlds, production collision and GPU command ordering."""
import copy
import binascii
import ctypes as c
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import unittest
from unittest.mock import patch,MagicMock
import tempfile
import profile_game
import portable_game
import sm64_castle
import world_assets
from test_player import Player,World,Floor,Wall,Point,fixture

ROOT=Path(__file__).resolve().parents[1]
class Transition(c.Structure):
    _fields_=[('source_area',c.c_uint16),('destination_area',c.c_uint16),
        ('position',c.c_int16*3),('arrival',c.c_int16*3),('radius',c.c_uint16),
        ('required_stars',c.c_uint16),('required_keys',c.c_uint16),('yaw',c.c_uint8),('automatic',c.c_uint8)]
class Exit(c.Structure):
    _fields_=[('source_area',c.c_uint16),('event',c.c_uint16),('destination_area',c.c_uint16),
        ('arrival',c.c_int16*3),('yaw',c.c_uint8)]

STUB=r'''
#include <stddef.h>
#include "world.h"
#include "gfx.h"
#include "gfx_protocol.h"
static uint32_t active,errors,drawn,cached,render_size,saved_size;
static unsigned char render_data[262144],saved_data[262144];
void render_reset(void){render_size=0;}
void render_save(void){saved_size=render_size;for(uint32_t i=0;i<saved_size && i<262144;++i)saved_data[i]=render_data[i];}
int render_same(void){if(render_size!=saved_size || render_size>262144)return 0;for(uint32_t i=0;i<render_size;++i)if(render_data[i]!=saved_data[i])return 0;return 1;}
static void render_bytes(const unsigned char *p,uint32_t n){for(uint32_t i=0;i<n;++i){if(render_size<262144)render_data[render_size]=p[i];++render_size;}}
#ifndef WORLD_FORCE_DIRECT
#define WORLD_FORCE_DIRECT 0
#endif
void *memcpy(void *d,const void *s,size_t n) { unsigned char *a=d;const unsigned char *b=s;for(size_t i=0;i<n;++i)a[i]=b[i];return d; }
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n) {
    render_bytes(&op,1);render_bytes(&n,1);render_bytes(p,n);
    if(op==GFX_OP_UPLOAD_VERTICES || op==GFX_OP_UPLOAD_INDICES) { if(active)++errors; }
    else if(op==GFX_OP_DRAW_TRIANGLE) {
        if(!active || n!=19)++errors;
        for(uint32_t i=0;i<3;++i) {
            int16_t z=(int16_t)(((uint16_t)p[6*i+4]<<8)|p[6*i+5]);
            if(z<256)++errors;
        }
        ++drawn;
    }else ++errors;
    return 0;
}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t) { if(active || h>=16 || v>128 || t>256)++errors;return 0; }
int gfx_draw_matrix(uint8_t h,const int16_t m[12]) { render_bytes(&h,1);render_bytes((const unsigned char*)m,24);if(!active)++errors;++cached;return 0; }
static const scene_vertex_t points[]={{-20,0,400},{0,20,400},{20,0,400}};
static const scene_triangle_t triangles[]={{0,1,2,1}};
static const world_chunk_t chunks[]={
    {{points,triangles,3,1},{0,0,0},{-20,20,0,20,400,400},0,0},
    {{points,triangles,3,1},{0,0,0},{-20,20,0,20,400,400},0,0},
    {{points,triangles,3,1},{0,0,0},{-20,20,0,20,400,400},0,0}};
static const player_world_t physics={0,0,0,0,0,0,0,8,18,128,12,3,30,-1500};
static const world_area_t area={chunks,3,&physics,0,0,0,0,0,0,0,0,0,0,0,0,0};
int cache_fixture(void) {
    player_t p={0};int16_t v[12]={256,0,0,0,0,256,0,0,0,0,256,0};
    active=errors=drawn=cached=0;world_select(&area,&p);
    // Only one cache handle remains. Every other visible face must still draw.
    if(world_prepare(&area,&p,v,15))return -1;
    active=1;if(world_draw(&area,&p,v,15))return -2;active=0;
    if(errors || cached!=(WORLD_FORCE_DIRECT?0u:1u) || drawn!=(WORLD_FORCE_DIRECT?3u:2u))return -3;
    cached=drawn=0;
    if(world_prepare(&area,&p,v,15))return -4;
    active=1;if(world_draw(&area,&p,v,15))return -5;active=0;
    return errors || cached!=(WORLD_FORCE_DIRECT?0u:1u) || drawn!=(WORLD_FORCE_DIRECT?3u:2u)?-6:0;
}
int deferred_fixture(void) {
    static const world_chunk_t ch={ {points,triangles,3,1},{0,0,0},{-20,20,0,20,400,400},0,WORLD_RENDER_DEFERRED };
    static const world_area_t a={&ch,1,&physics,0,0,0,0,0,0,0,0,0,0,0,0,0};
    player_t p={0};int16_t v[12]={256,0,0,0,0,256,0,0,0,0,256,0};
    active=errors=drawn=cached=0;render_reset();world_select(&a,&p);
    if(world_prepare(&a,&p,v,15))return -1;
    active=1;if(world_draw(&a,&p,v,15))return -2;active=0;
    return errors || drawn || cached || render_size?-3:0;
}
int clip_fixture(void) {
    player_t p={0};int16_t v[12]={256,0,0,0,0,256,0,0,0,0,256,0};
    // Chunk translation exceeds int16; a small piece of the original face is
    // nevertheless visible. It must use the clipped direct path, not wrap.
    static const scene_vertex_t large[]={{-10000,0,1000},{10000,0,1000},{0,100,1000}};
    static const world_chunk_t ch={{large,triangles,3,1},{0,0,0},{-10000,10000,0,100,1000,1000},0,0};
    static const world_area_t a={&ch,1,&physics,0,0,0,0,0,0,0,0,0,0,0,0,0};
    active=errors=drawn=cached=0;world_select(&a,&p);
    if(world_prepare(&a,&p,v,15))return -1;
    active=1;if(world_draw(&a,&p,v,15))return -2;active=0;
    return errors || !drawn || cached?-3:0;
}
int contact_fixture(void) {
    static const collision_floor_t f={ {-100,0,-100},{-100,0,100},{100,0,100},-100,100,-100,100,0,0 };
    static const int16_t n[][3]={{0,4096,0}};
    static const world_surface_t s={10,42,-123,3,0};
    static const player_world_t w={&f,0,1,0,0,0,0,8,18,128,12,3,30,-1500};
    static const world_area_t a={0,0,&w,0,0,0,0,0,0,0,0,0,n,0,&s,0};
    player_t p={0};p.z=20;world_contact_t contact;
    if(!world_floor_contact(&a,&p,&contact) || contact.height || contact.surface!=&s || contact.normal!=n[0])return -1;
    p.x=101;
    return world_floor_contact(&a,&p,&contact) || contact.surface || contact.normal?-2:0;
}
'''

class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'build/world-tests';out.mkdir(parents=True,exist_ok=True)
        stub=out/'stub.c';stub.write_text(STUB)
        dll=out/('world.dll' if os.name=='nt' else 'world.so')
        exports=['deferred_fixture','cache_fixture','clip_fixture','contact_fixture','player_bind_query','player_floor','player_step','player_reset','world_transition_find','world_exit_find','castle_floor_event']
        flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-Ifirmware/include','-Ifirmware/generated']
        flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry',*['-Wl,/export:'+n for n in exports]] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,'firmware/src/world.c','firmware/src/player.c',
            'firmware/src/game_services.c','firmware/ports/castle_rules.c',str(stub),'-o',str(dll)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(dll))
        direct_dll=out/('world-direct.dll' if os.name=='nt' else 'world-direct.so')
        subprocess.run([shutil.which('clang'),*flags,'-DWORLD_FORCE_DIRECT=1',
            'firmware/src/world.c','firmware/src/player.c','firmware/src/game_services.c',
            'firmware/ports/castle_rules.c',str(stub),'-o',str(direct_dll)],cwd=ROOT,check=True)
        cls.direct=c.CDLL(str(direct_dll))
        cls.lib.player_bind_query.argtypes=[c.POINTER(World),c.POINTER(c.c_uint16),c.c_uint32,
            c.POINTER(c.c_uint16),c.c_uint32,c.c_int32,c.POINTER(c.c_int16*3)]
        cls.lib.player_floor.argtypes=[c.POINTER(World),c.c_int32,c.c_int32,c.c_int32]
        cls.lib.player_step.argtypes=[c.POINTER(Player),c.POINTER(World),c.c_uint32]
        cls.lib.player_reset.argtypes=[c.POINTER(Player),c.POINTER(World)]
        cls.lib.world_transition_find.argtypes=[c.POINTER(Transition),c.c_uint32,c.c_uint32,c.POINTER(Player),c.c_uint32,c.c_uint32,c.c_uint32]
        cls.lib.world_exit_find.argtypes=[c.POINTER(Exit),c.c_uint32,c.c_uint32,c.c_uint32];cls.lib.world_exit_find.restype=c.POINTER(Exit)
        cls.lib.castle_floor_event.argtypes=[c.c_uint16,c.c_int32,c.c_int32];cls.lib.castle_floor_event.restype=c.c_uint32
        crc_source=out/'crc.c'
        crc_source.write_text('#include <stdint.h>\n#define SOC_H\n'+
            'static volatile uint32_t test_regs[6];\n'+
            '\n'.join('#define '+name+' test_regs['+str(i)+']' for i,name in enumerate(('GFX_ERRORS','GFX_STATUS','GFX_DATA','GFX_FRAME_ID','GFX_ACK','SOC_UNUSED')))+
            '\n#define GFX_TX_READY 1u\n#define GFX_FRAME_DONE 4u\n#include "'+(ROOT/'firmware/src/gfx.c').as_posix()+'"\n'+
            'uint16_t crc_test_byte(uint16_t seed,uint8_t value){return crc_byte(seed,value);}\n')
        crc_dll=out/('crc.dll' if os.name=='nt' else 'crc.so')
        crc_flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated']
        crc_flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:crc_test_byte'] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*crc_flags,str(crc_source),'-o',str(crc_dll)],cwd=ROOT,check=True)
        cls.crc=c.CDLL(str(crc_dll));cls.crc.crc_test_byte.argtypes=[c.c_uint16,c.c_uint8];cls.crc.crc_test_byte.restype=c.c_uint16
        edge_source=out/'edge.c'
        edge_source.write_text('#include "'+(ROOT/'firmware/src/player.c').as_posix()+'"\n'+
            'int edge_probe(collision_point_t p,collision_point_t a,collision_point_t b,int32_t radius){return edge_hit(p,a,b,fixed_mul(radius,radius));}\n')
        edge_dll=out/('edge.dll' if os.name=='nt' else 'edge.so')
        edge_flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include']
        edge_flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:edge_probe'] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*edge_flags,str(edge_source),'-o',str(edge_dll)],cwd=ROOT,check=True)
        cls.edge=c.CDLL(str(edge_dll));cls.edge.edge_probe.argtypes=[Point,Point,Point,c.c_int32]
        # Build the real castle update path against an isolated copy of its
        # source-derived world, so another game's generated headers cannot
        # change this integration test's terrain or actor package.
        scene=json.loads((ROOT/'build/castle/world.json').read_text())
        actors,palette,_,_,report,areas=world_assets.compile_world(scene)
        (out/'world_data.h').write_text(world_assets.header(areas))
        resident=portable_game.header(actors,palette,[],[],{**report,'collision_floors':0,'collision_walls':0})
        (out/'portable_data.h').write_text(resident.replace('#ifdef PORTABLE_DATA_DEFINE','#include "world_data.h"\n#ifdef PORTABLE_DATA_DEFINE',1))
        for name in ('castle_actor_data.h','castle_transitions.h','castle_surface_types.h'):
            shutil.copyfile(ROOT/'firmware/generated'/name,out/name)
        route_source=out/'route.c'
        route_source.write_text('#define SOC_H\n#define SOC_CYCLES 0u\n#define PORTABLE_DATA_DEFINE\n#include "portable_data.h"\n#include "castle_surface_types.h"\n'+
            '#include "'+(ROOT/'firmware/ports/castle.c').as_posix()+'"\n'+r'''
int gfx_identity_view(void){return 0;}
int gfx_begin_frame(uint32_t frame){(void)frame;return 0;}
int gfx_end_frame(void){return 0;}
void render_reset(void);void render_save(void);int render_same(void);
static uint32_t state_hash(const void *data,uint32_t size) {
    const unsigned char *p=data;uint32_t h=2166136261u;
    for(uint32_t i=0;i<size;++i)h=(h^p[i])*16777619u;
    return h;
}
static uint32_t logic_hash(void) {
    return state_hash(&player,sizeof(player))^state_hash(&view,sizeof(view))^
        state_hash(&animation,sizeof(animation))^state_hash(&camera,sizeof(camera))^
        current_area^previous_buttons^transition_cooldown^pending_event^pending_ticks;
}
int castle_repeat_render_fixture(void) {
    if(game_port_init())return -1;
    for(uint32_t tick=0;tick<40;++tick) {
        game_port_update(tick<20?0:1);
        uint32_t before=logic_hash();
        render_reset();if(game_port_render(1))return -2;
        render_save();
        uint32_t pose=state_hash(posed,sizeof(posed));
        render_reset();if(game_port_render(2))return -3;
        if(!render_same())return -6;
        if(before!=logic_hash())return -4;
        if(pose!=state_hash(posed,sizeof(posed)))return -5;
    }
    return 0;
}
int castle_interpolation_fixture(void) {
    if(game_port_init())return -1;
    for(uint32_t tick=0;tick<20;++tick)game_port_update(0);
    game_port_update(1);
    uint32_t state=logic_hash();
    if(game_port_render_interpolated(1,0))return -2;
    for(uint32_t i=0;i<GAME_ANIMATION_VERTICES;++i)
        if(posed[i].x!=pose_previous[i].x || posed[i].y!=pose_previous[i].y || posed[i].z!=pose_previous[i].z)return -3;
    if(game_port_render_interpolated(2,65536))return -4;
    for(uint32_t i=0;i<GAME_ANIMATION_VERTICES;++i)
        if(posed[i].x!=pose_current[i].x || posed[i].y!=pose_current[i].y || posed[i].z!=pose_current[i].z)return -5;
    if(game_port_render_interpolated(3,32768) || state!=logic_hash())return -6;
    render_reset();if(game_port_render(4))return -7;render_save();
    render_reset();if(game_port_render_interpolated(5,65536) || !render_same())return -8;
    int16_t arrival[3]={-1023,0,1152};enter_area(1,arrival,0);camera_update();render_capture(1);
    if(render_previous_player.x!=player.x || render_previous_player.y!=player.y || render_previous_view.yaw!=view.yaw)return -9;
    return 0;
}
int castle_camera_fixture(void) {
    if(game_port_init())return -1;
    if(view.view[9]>=0)return -2;
    int32_t foot=120-(256*view.view[7])/view.view[11];
    int32_t head_y=((720*view.view[5])>>8)+view.view[7];
    int32_t head_z=((720*view.view[9])>>8)+view.view[11];
    if(head_z<=257)return -3;
    int32_t head=120-(256*head_y)/head_z;
    if(head<80 || foot>190 || foot-head<30 || foot-head>70)return -4;
    game_port_update(0x80000000u); // Mouse neutral must retain the downward framing.
    if(view.pitch>=0)return -5;
    int16_t arrival[3]={-1023,0,1152};enter_area(1,arrival,0);
    if(camera.initialized)return -6;
    camera_update();
    return camera.focus_x!=player.x || camera.focus_z!=player.z?-7:0;
}
int castle_return_fixture(void) {
    if(game_port_init())return -1;
    for(uint32_t tick=0;tick<40;++tick)game_port_update(0);
    if(current_area || pending_event)return -2;
    const world_area_t *a=world_areas+4;
    uint32_t floor=a->physics->floor_count;
    for(uint32_t i=0;i<a->physics->floor_count;++i)
        if(a->floor_surfaces[i].type==CASTLE_SURFACE_DEATH_PLANE){floor=i;break;}
    if(floor==a->physics->floor_count)return -3;
    const collision_floor_t *f=a->physics->floors+floor;
    int16_t arrival[3]={(int16_t)((f->a.x+f->b.x+f->c.x)/3),
        (int16_t)(f->a.y+2047),(int16_t)((f->a.z+f->b.z+f->c.z)/3)};
    enter_area(4,arrival,0);transition_cooldown=0;
    game_port_update(0);
    if(current_area!=4 || pending_event!=CASTLE_EXIT_FALL || pending_ticks!=20)return -4;
    for(uint32_t tick=0;tick<19;++tick)game_port_update(0);
    if(current_area!=4 || pending_ticks!=1)return -5;
    game_port_update(0);
    if(current_area!=1 || pending_event || pending_ticks)return -6;
    if(player.x!=-1024 || player.y!=900 || player.z!=717)return -7;
    if(castle_area!=1 || game_player.x!=player.x || game_player.y!=player.y)return -8;
    return 0;
}
''')
        route_dll=out/('route.dll' if os.name=='nt' else 'route.so')
        route_flags=['-DWORLD_FORCE_DIRECT=1','-shared','-O1','-ffreestanding','-fno-builtin','-I'+str(out),'-Ifirmware/include','-Ifirmware/generated']
        route_flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:castle_return_fixture','-Wl,/export:castle_camera_fixture','-Wl,/export:castle_repeat_render_fixture','-Wl,/export:castle_interpolation_fixture'] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*route_flags,str(route_source),str(stub),
            'firmware/src/world.c','firmware/src/player.c','firmware/src/camera.c','firmware/src/animation.c',
            'firmware/src/game_services.c','firmware/ports/castle_rules.c','-o',str(route_dll)],cwd=ROOT,check=True)
        cls.route=c.CDLL(str(route_dll))

    def setUp(self):self.lib.player_bind_query(None,None,0,None,0,4096,None)

    def test_deferred_appearance_emits_no_upload_or_draw_on_both_paths(self):
        self.assertEqual(self.lib.deferred_fixture(),0)
        self.assertEqual(self.direct.deferred_fixture(),0)

    def test_render_flags_partition_preserves_all_faces(self):
        vertices=[[0,0,400],[0,20,400],[20,0,400]]
        triangles=[[0,1,2,1]]*4
        result=world_assets.chunks(vertices,triangles,render_flags=[0,1,0,1])
        self.assertEqual(sorted(i for ch in result for i in ch['source_triangles']),list(range(4)))
        for ch in result:
            self.assertTrue(all([0,1,0,1][i]==ch['render_flags'] for i in ch['source_triangles']))
        self.assertTrue(all(ch['render_flags']==0 for ch in world_assets.chunks(vertices,triangles)))

    def test_world_rejects_malformed_render_flags(self):
        scene=json.loads((ROOT/'build/castle/world.json').read_text())
        n=len(scene['areas'][0]['triangles'])
        for flags in ([0]*(n-1),[2]*n,[True]*n):
            scene['areas'][0]['triangle_render_flags']=flags
            with self.assertRaisesRegex(ValueError,'render flags'):world_assets.compile_world(scene)

    def test_cache_overflow_keeps_all_visible_faces_and_uploads_between_frames(self):
        self.assertEqual(self.lib.cache_fixture(),0)

    def test_direct_diagnostic_keeps_all_visible_faces_without_terrain_mesh_draws(self):
        self.assertEqual(self.direct.cache_fixture(),0)
        self.assertEqual(self.direct.clip_fixture(),0)

    def test_large_visible_face_clips_instead_of_wrapping_or_dropping(self):
        self.assertEqual(self.lib.clip_fixture(),0)

    def test_indexed_floor_matches_full_scan(self):
        w=fixture();indices=(c.c_uint16*2)(1,0)
        for x,z in [(random.Random(i).randint(-1100,1100),random.Random(i+300).randint(-1100,1100)) for i in range(100)]:
            self.lib.player_bind_query(None,None,0,None,0,4096,None)
            expected=self.lib.player_floor(c.byref(w),x,z,500)
            self.lib.player_bind_query(c.byref(w),indices,2,None,0,4096,None)
            self.assertEqual(self.lib.player_floor(c.byref(w),x,z,500),expected)

    def test_indexed_wall_movement_matches_full_scan(self):
        a=fixture('wall');b=fixture('wall');pa=Player();pb=Player()
        self.lib.player_reset(c.byref(pa),c.byref(a));self.lib.player_reset(c.byref(pb),c.byref(b))
        fi=(c.c_uint16*a.floor_count)(*range(a.floor_count));wi=(c.c_uint16*a.wall_count)(*reversed(range(a.wall_count)))
        for keys in [2]*25+[4]*25+[1|16]+[1]*20:
            self.lib.player_bind_query(None,None,0,None,0,4096,None)
            self.lib.player_step(c.byref(pa),c.byref(a),keys)
            self.lib.player_bind_query(c.byref(b),fi,b.floor_count,wi,b.wall_count,16000,None)
            self.lib.player_step(c.byref(pb),c.byref(b),keys)
            self.assertEqual(bytes(pa),bytes(pb))

    def test_plane_normals_support_steep_floor(self):
        w=fixture(slope=True);normals=((c.c_int16*3)*2)(*((c.c_int16*3)(-1024,4096,0) for _ in range(2)))
        self.lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
        self.assertEqual(self.lib.player_floor(c.byref(w),400,0,1000),100)

    def test_horizontal_motion_cannot_enter_rising_floor_plane(self):
        vertices=[(-1000,-2000,-1000),(-1000,-2000,1000),
                  (1000,2000,1000),(1000,2000,-1000)]
        fs=(Floor*2)(*(Floor(*(Point(*vertices[i]) for i in tri),
                            -1000,1000,-1000,1000,8192,0)
                       for tri in ((0,1,2),(0,2,3))))
        w=World(fs,None,2,0,0,0,0,24,60,180,32,4,42,-16000)
        normals=((c.c_int16*3)*2)(*((c.c_int16*3)(-3664,1832,0) for _ in range(2)))
        try:
            self.lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
            p=Player(0,0,0,0,1,0,0,0)
            for _ in range(20):self.lib.player_step(c.byref(p),c.byref(w),2)
            self.assertEqual((p.x,p.y,p.grounded,p.respawns),(0,0,1,0))
            # An airborne character must not enter the same ramp horizontally.
            p=Player(0,10,0,-1,0,0,0,0)
            self.lib.player_step(c.byref(p),c.byref(w),2)
            self.assertEqual((p.x,p.y,p.grounded),(0,9,0))
            # A smaller allowed step still follows the unchanged surface.
            w.speed=8;p=Player(0,0,0,0,1,0,0,0)
            self.lib.player_step(c.byref(p),c.byref(w),2)
            self.assertEqual((p.x,p.y,p.grounded),(8,16,1))
        finally:self.lib.player_bind_query(None,None,0,None,0,4096,None)

    def test_original_castle_interior_slope_rejects_33_unit_step(self):
        pts=[(102,1024,-1637),(-511,1415,-1302),(-511,1024,-1023)]
        fs=(Floor*1)(Floor(*(Point(*p) for p in pts),-511,102,-1637,-1023,0,0))
        w=World(fs,None,1,0,-307,1155,-1321,24,60,180,32,4,42,-16000)
        normals=((c.c_int16*3)*1)((c.c_int16*3)(2588,1844,2584))
        try:
            self.lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
            self.assertEqual(self.lib.player_floor(c.byref(w),-331,-1321,16000),1188)
            p=Player(-307,1155,-1321,0,1,0,0,0)
            self.lib.player_step(c.byref(p),c.byref(w),1)
            self.assertEqual((p.x,p.y,p.z,p.grounded),(-307,1155,-1321,1))
        finally:self.lib.player_bind_query(None,None,0,None,0,4096,None)

    def test_horizontal_motion_below_overhead_floor_remains_allowed(self):
        w=fixture()
        fs=(Floor*4)(w.floors[0],w.floors[1],w.floors[0],w.floors[1])
        for f in fs[2:]:
            f.a.y=f.b.y=f.c.y=200
        w.floors=fs;w.floor_count=4
        self.lib.player_bind_query(None,None,0,None,0,4096,None)
        p=Player(0,0,0,0,1,0,0,0)
        for _ in range(10):self.lib.player_step(c.byref(p),c.byref(w),2)
        self.assertEqual((p.x,p.y,p.grounded),(80,0,1))

    def test_partition_preserves_triangle_ids_and_room_membership(self):
        v=[[-100,0,0],[0,100,0],[100,0,0]];t=[[0,1,2,1]]*300;m=[1]*150+[2]*150
        chunks=world_assets.chunks(v,t,m)
        self.assertEqual(sorted(i for ch in chunks for i in ch['source_triangles']),list(range(300)))
        self.assertEqual({ch['room_mask'] for ch in chunks},{1,2})
        self.assertTrue(all(len(ch['vertices'])<=128 and len(ch['triangles'])<=256 for ch in chunks))

    def test_actor_only_resident_scene_requires_custom_port(self):
        scene=json.loads((ROOT/'examples/portable-room/scene.json').read_text())
        scene['meshes']=scene['meshes'][:1];scene['meshes'][0]['role']='actor';scene.pop('controller')
        scene['projection']={'focal':256,'near_z':257}
        result=portable_game.compile_scene(scene,False)
        self.assertEqual(result[2:4],([],[]))
        with self.assertRaises(ValueError):portable_game.compile_scene(scene,True)

    def test_texture_include_policy_cannot_hide_geometry_include(self):
        texture='static const Texture color[]={\n#include "levels/castle_grounds/3.rgba16.inc.c"\n};'
        self.assertNotIn('#include',sm64_castle.region(texture))
        with self.assertRaises(ValueError):sm64_castle.region('#include "geometry.inc.c"')

    def test_region_selects_us_and_checks_balance(self):
        self.assertEqual(sm64_castle.region('#ifdef VERSION_JP\nJP\n#else\nUS\n#endif'),'US')
        for text in ('#endif','#else','#ifdef SOMETHING\nX\n#endif'):
            with self.assertRaises(ValueError):sm64_castle.region(text)

    def test_original_collision_count_and_rooms(self):
        path=ROOT/'external/sm64/levels/castle_inside/areas/1'
        data=sm64_castle.collision(path/'collision.inc.c',path/'room.inc.c')
        self.assertEqual(len(data['triangles']),2144)
        self.assertGreater(max(t[4] for t in data['triangles']),1)
        self.assertEqual(len(data['special_objects']),11)

    def test_source_warps_resolve_castle_slide_and_key_gates(self):
        world=json.loads((ROOT/'build/castle/world.json').read_text())
        ts,unsupported=sm64_castle.transitions(ROOT/'external/sm64',world['areas'])
        self.assertTrue(any(t['source_area']==1 and t['destination_area']==4 and t['source_node']==10 for t in ts))
        self.assertTrue(any(t['destination_area']==2 and t['required_keys']==1 for t in ts))
        self.assertTrue(any(t['destination_area']==3 and t['required_keys']==2 for t in ts))
        self.assertTrue(unsupported)
        self.assertFalse(any(t['arrival']==[0,0,0] for t in ts))

    def test_world_compiler_has_no_source_game_dependency(self):
        scene=json.loads((ROOT/'examples/portable-world/world.json').read_text())
        result=world_assets.compile_world(scene)
        self.assertEqual(result[-2]['areas'],2)
        self.assertEqual(result[-2]['stored_world_triangles'],4)
        self.assertIn('world_1_chunks',world_assets.header(result[-1]))
        invalid=copy.deepcopy(scene);invalid['areas'][0]['physics']={'speed':100,'radius':100,'height':200,'step_height':20,'gravity':4,'jump_speed':42,'kill_y':-16000}
        with self.assertRaises(ValueError):world_assets.compile_world(invalid)

    def test_transition_requires_use_and_progress_and_checks_area(self):
        t=Transition(0,1,(c.c_int16*3)(0,0,0),(c.c_int16*3)(800,0,800),100,8,2,128,0);p=Player()
        call=self.lib.world_transition_find
        self.assertEqual(call(c.byref(t),1,0,c.byref(p),0,70,3),-1)
        self.assertEqual(call(c.byref(t),1,0,c.byref(p),1,7,3),-2)
        self.assertEqual(call(c.byref(t),1,0,c.byref(p),1,70,1),-2)
        self.assertEqual(call(c.byref(t),1,0,c.byref(p),1,70,3),0)
        self.assertEqual(call(c.byref(t),1,1,c.byref(p),1,70,3),-1)
        p.x=101;self.assertEqual(call(c.byref(t),1,0,c.byref(p),1,70,3),-1)

    def test_automatic_warp_needs_no_use_button(self):
        t=Transition(0,1,(c.c_int16*3)(0,0,0),(c.c_int16*3)(800,0,800),50,0,0,0,1);p=Player()
        self.assertEqual(self.lib.world_transition_find(c.byref(t),1,0,c.byref(p),0,0,0),0)

    def test_original_world_geometry_reconstructs_without_changed_faces(self):
        source=json.loads((ROOT/'build/castle/world.json').read_text())
        result=world_assets.compile_world(source)
        for a in result[-1]:
            recovered={}
            for ch in a['chunks']:
                for face,original in zip(ch['triangles'],ch['source_triangles']):
                    points=[[ch['vertices'][k][axis]+ch['origin'][axis] for axis in range(3)] for k in face[:3]]
                    recovered[original]=(points,face[3])
            self.assertEqual(len(recovered),len(a['triangles']))
            for i,t in enumerate(a['triangles']):self.assertEqual(recovered[i],([a['vertices'][k] for k in t[:3]],t[3]))

    def test_original_area_grid_queries_match_exhaustive_plane_queries(self):
        source=json.loads((ROOT/'build/castle/world.json').read_text())
        for a in world_assets.compile_world(source)[-1]:
            fs=(Floor*len(a['floors']))(*(Floor(*(Point(*p) for p in pts),*r) for pts,r in a['floors']))
            ws=(Wall*len(a['walls']))(*(Wall(*(Point(*p) for p in pts),*r) for pts,r in a['walls']))
            w=World(fs,ws,len(fs),len(ws),*a['spawn'],24,60,180,32,4,42,-16000)
            normals=((c.c_int16*3)*len(fs))(*((c.c_int16*3)(*n) for n in a['floor_normals']))
            fi=(c.c_uint16*len(a['floor_indices']))(*a['floor_indices']);wi=(c.c_uint16*len(a['wall_indices']))(*a['wall_indices'])
            rng=random.Random(42)
            for _ in range(100):
                pts,_=a['floors'][rng.randrange(len(fs))]
                x=sum(p[0] for p in pts)//3;z=sum(p[2] for p in pts)//3;ceiling=sum(p[1] for p in pts)//3+256
                self.lib.player_bind_query(c.byref(w),None,0,None,0,16000,normals)
                expected=self.lib.player_floor(c.byref(w),x,z,ceiling)
                cx=(x-a['grid_origin'][0])//512;cz=(z-a['grid_origin'][1])//512
                start_f,nf,start_w,nw=a['grid'][cz*a['grid_size'][0]+cx]
                fptr=c.cast(c.byref(fi,start_f*2),c.POINTER(c.c_uint16));wptr=c.cast(c.byref(wi,start_w*2),c.POINTER(c.c_uint16))
                self.lib.player_bind_query(c.byref(w),fptr,nf,wptr,nw,16000,normals)
                self.assertEqual(self.lib.player_floor(c.byref(w),x,z,ceiling),expected,(a['id'],x,z))

    def test_production_crc_matches_reference_for_all_bytes_and_seed_samples(self):
        for seed in (0,1,0x1021,0x7fff,0x8000,0xabcd,0xffff):
            for value in range(256):
                self.assertEqual(self.crc.crc_test_byte(seed,value),binascii.crc_hqx(bytes([value]),seed))
        crc=0xffff
        for value in b'123456789':crc=self.crc.crc_test_byte(crc,value)
        self.assertEqual(crc,0x29b1)

    def test_long_collision_edge_does_not_overflow_fraction(self):
        # Midpoint dot*256 is 12.8 billion; the old shifted numerator wrapped.
        a=Point(-5000,0,0);b=Point(5000,0,0)
        self.assertEqual(self.edge.edge_probe(Point(0,20,0),a,b,60),1)
        self.assertEqual(self.edge.edge_probe(Point(0,80,0),a,b,60),0)
        self.assertEqual(self.edge.edge_probe(Point(-5100,0,0),a,b,60),0)

    def test_contact_reports_source_surface_and_no_floor(self):
        self.assertEqual(self.lib.contact_fixture(),0)

    def test_source_surface_types_and_special_parameters_survive_compile(self):
        source=json.loads((ROOT/'build/castle/world.json').read_text())
        types=sm64_castle.surface_types(ROOT/'external/sm64')
        for a in world_assets.compile_world(source)[-1]:
            for m in a['floor_metadata']+a['wall_metadata']:
                self.assertEqual(m['type'],types[m['surface']])
                self.assertEqual(m['force'],a['collision']['triangle_forces'][m['source']])
                self.assertEqual(m['room'],a['collision']['triangles'][m['source']][4])
        example=json.loads((ROOT/'examples/portable-world/world.json').read_text())
        for area in example['areas']:
            tag=area['collision']['triangles'][0][3]
            area['collision']['surface_types']={tag:1234}
            area['collision']['triangle_forces']=[-123]*len(area['collision']['triangles'])
        result=world_assets.compile_world(example)
        self.assertTrue(all(m['type']==1234 and m['force']==-123 for a in result[-1] for m in a['floor_metadata']))
        self.assertIn('{1234,0,-123,0,0}',world_assets.header(result[-1]))
        example['areas'][0]['collision']['triangle_forces']=[]
        with self.assertRaises(ValueError):world_assets.compile_world(example)

    def test_slide_falling_exit_uses_original_f3_destination(self):
        source=json.loads((ROOT/'build/castle/world.json').read_text())
        exits=sm64_castle.event_exits(ROOT/'external/sm64',source['areas'])
        slide=[t for t in exits if t['source_area']==4]
        self.assertEqual({t['event'] for t in slide},{0xf0,0xf1,0xf3})
        fall=next(t for t in slide if t['event']==0xf3)
        self.assertEqual((fall['destination_area'],fall['destination_node']),(1,0x20))
        self.assertEqual(fall['arrival'],[-1024,900,717])
        records=(Exit*len(exits))(*(Exit(t['source_area'],t['event'],t['destination_area'],(c.c_int16*3)(*t['arrival']),t['yaw']) for t in exits))
        selected=self.lib.world_exit_find(records,len(records),4,0xf3)
        self.assertTrue(selected);self.assertEqual(list(selected.contents.arrival),fall['arrival'])
        self.assertFalse(self.lib.world_exit_find(records,len(records),4,1))

    def test_original_death_barrier_threshold_and_warp_floor_event(self):
        event=self.lib.castle_floor_event
        self.assertEqual(event(0x0a,-7986,-10034),0)
        self.assertEqual(event(0x0a,-7987,-10034),0xf3)
        self.assertEqual(event(0x38,2047,0),0xf3)
        self.assertEqual(event(0x32,5000,0),0xf3)
        for ordinary in (0,0x13,0x33,0x34):self.assertEqual(event(ordinary,0,0),0)

    def test_castle_update_returns_from_slide_after_original_twenty_ticks(self):
        self.assertEqual(self.route.castle_return_fixture(),0)

    def test_interpolation_endpoints_do_not_mutate_game_and_reset_on_transition(self):
        self.assertEqual(self.route.castle_interpolation_fixture(),0)

    def test_repeated_castle_render_preserves_simulation_and_pose(self):
        self.assertEqual(self.route.castle_repeat_render_fixture(),0)

    def test_castle_camera_frames_character_and_resets_on_area_change(self):
        self.assertEqual(self.route.castle_camera_fixture(),0)

    def test_profiler_restores_baseline_when_trial_upload_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory);trial=path/'trial.json';restore=path/'restore.json';symbols=path/'symbols.json'
            trial.write_text('{}');restore.write_text('{}');symbols.write_text('{"game_frame":128}')
            loader=MagicMock();loader.transfer.side_effect=[RuntimeError('upload failure'),None]
            with patch.object(profile_game.load_game,'package_segments',side_effect=[['trial'],['baseline']]), \
                 patch.object(profile_game.load_game,'require_hardware'), \
                 patch.object(profile_game.load_game,'Loader',return_value=loader):
                with self.assertRaisesRegex(RuntimeError,'upload failure'):
                    profile_game.profile(trial,restore,symbols,path/'report.json',warmup=0)
            self.assertEqual([call.args[0] for call in loader.transfer.call_args_list],[['trial'],['baseline']])
            loader.close.assert_called_once()

if __name__=='__main__':unittest.main()
