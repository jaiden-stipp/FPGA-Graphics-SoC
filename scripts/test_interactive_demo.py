"""Native production-module interaction checks plus source/transport contracts."""
import binascii
import ctypes as c
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import load_game
import mouse_udp
import portable_game
import quake_assets
import quake_demo
from test_player import Player

ROOT=Path(__file__).resolve().parents[1]
class InteractiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory(dir=ROOT/'build');out=Path(cls.directory.name)
        cls.spec,_,_,compiled,_,_=portable_game.project(ROOT/'build/quake-interactive/game.project.json')
        (out/'portable_data.h').write_text(portable_game.header(*compiled))
        cls.commands=[]
        (out/'fixture.c').write_text('''#include "game_services.h"
static unsigned commands,triangles,uploads,active;static short current_view[12];static int minimum_depth;
int gfx_command(unsigned char op,const unsigned char *p,unsigned char n){
    ++commands;if(op==2){if(n!=19 || !active)return -1;++triangles;
      for(unsigned i=0;i<3;++i){unsigned b=6*i;int x=(short)((p[b]<<8)|p[b+1]),y=(short)((p[b+2]<<8)|p[b+3]),z=(short)((p[b+4]<<8)|p[b+5]);
        int depth=((current_view[8]*x+current_view[9]*y+current_view[10]*z)>>8)+current_view[11];if(depth<minimum_depth)minimum_depth=depth;}}
    if(op==9){if(n!=3+6*p[2] || p[1]+p[2]>128)return -1;++uploads;}return 0;
}
int gfx_identity_view(void){return active?-1:0;}
int gfx_projection(short f,short n){return active||f<128||n<257;}
int gfx_view_matrix(const short *m){if(active)return -1;for(unsigned i=0;i<12;++i)current_view[i]=m[i];return 0;}
int gfx_begin_frame(unsigned f){(void)f;if(active)return -1;active=1;minimum_depth=32767;return 0;}
int gfx_end_frame(void){active=0;return 0;}
int gfx_draw_mesh(unsigned char h,short x,short y,short z){(void)h;(void)x;(void)y;(void)z;return 0;}
int gfx_draw_matrix(unsigned char h,const short *m){(void)h;(void)m;return 0;}
#include "quake_demo.c"
void pose(int x,int z){player.x=x;player.z=z;player.y=player_floor(&portable_world,x,z,512);player.velocity_y=0;player.grounded=1;game_player=player;}
int enemy_axis(unsigned axis){return axis==0?enemy.x:axis==1?enemy.y+112:enemy.z;}
unsigned counter(unsigned index){return index==0?triangles:index==1?uploads:index==3?(unsigned)minimum_depth:commands;}
''')
        cls.dll=out/('demo.dll' if os.name=='nt' else 'demo.so')
        exported=['game_port_init','game_port_update','game_port_render','pose','enemy_axis','counter','demo_state','game_player',
            'game_object_overlap','game_door_step','game_pickup_step','game_animation_frame','game_view_update','game_input_decode','game_movement_keys']
        flags=['-shared','-O1','-Wall','-Wextra','-Werror','-I'+str(out),'-I'+str(ROOT/'firmware/ports'),
            '-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated')]
        if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+s for s in exported]
        else:flags+=['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(out/'fixture.c'),str(ROOT/'firmware/src/game_services.c'),
            str(ROOT/'firmware/src/player.c'),str(ROOT/'firmware/src/portable_assets.c'),'-o',str(cls.dll)],check=True)
        if os.name=='nt':
            cls.memory=c.WinDLL('kernel32',use_last_error=True)
            cls.memory.VirtualAlloc.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32,c.c_uint32];cls.memory.VirtualAlloc.restype=c.c_void_p
            cls.mapping=cls.memory.VirtualAlloc(0x40000000,4096,0x3000,4)
        else:
            cls.memory=c.CDLL(None);cls.memory.mmap.argtypes=[c.c_void_p,c.c_size_t,c.c_int,c.c_int,c.c_int,c.c_long];cls.memory.mmap.restype=c.c_void_p
            cls.mapping=cls.memory.mmap(0x40000000,4096,3,0x100022,-1,0)
        if cls.mapping!=0x40000000:raise RuntimeError('Cannot reserve test-only MMIO page')
        c.c_uint32.from_address(0x40000064).value=0x494e0101
        cls.lib=c.CDLL(str(cls.dll));cls.lib.game_port_update.argtypes=[c.c_uint32]
        cls.lib.pose.argtypes=[c.c_int,c.c_int];cls.lib.enemy_axis.argtypes=[c.c_uint32]
        cls.state=(c.c_uint32*10).in_dll(cls.lib,'demo_state')
        cls.player=Player.in_dll(cls.lib,'game_player')
    @classmethod
    def tearDownClass(cls):
        if os.name=='nt':
            from _ctypes import FreeLibrary
            FreeLibrary(cls.lib._handle);cls.memory.VirtualFree.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32]
            cls.memory.VirtualFree(cls.mapping,0,0x8000)
        else:
            cls.memory.munmap.argtypes=[c.c_void_p,c.c_size_t];cls.memory.munmap(cls.mapping,4096)
        cls.directory.cleanup()
    def setUp(self):
        self.assertEqual(self.lib.game_port_init(),0);self.update()
    def update(self,buttons=0,yaw=0,pitch=0):
        self.lib.game_port_update(0x80000000|((pitch&255)<<16)|(yaw<<8)|buttons)
    def test_packet_absolute_angles_and_crc(self):
        wire=mouse_udp.packet(123,255,0xf4,128,-32);cmd=wire[12:]
        self.assertEqual(cmd[5:12],b'IN\x01\xff\xf4\x80\xe0')
        self.assertEqual(cmd[12:29],bytes(17));self.assertEqual(struct.unpack('>H',cmd[-2:])[0],binascii.crc_hqx(cmd[:-2],0xffff))
        for args in [(0,0,256,0,0),(0,0,0,256,0),(0,0,0,0,33)]:
            with self.assertRaises(ValueError):mouse_udp.packet(*args)
    def test_mouse_look_stable_without_repeated_deltas(self):
        self.update(yaw=32,pitch=12);self.assertEqual((self.state[7],self.state[8]),(32,12))
        for _ in range(5):self.update(yaw=32,pitch=12)
        self.assertEqual((self.state[7],self.state[8]),(32,12))
    def test_camera_relative_strafe_jump_and_reset(self):
        self.update(2);self.assertGreater(self.player.x,0);self.assertEqual(self.player.z,400)
        self.update(16);self.assertGreater(self.player.y,-64)
        self.update(128);self.update();self.assertEqual((self.player.x,self.player.y,self.player.z),(0,-64,400))
    def test_pickup_fires_once(self):
        self.lib.pose(0,600);self.update();self.assertEqual((self.state[1],self.state[4]),(50,0))
        for _ in range(10):self.update()
        self.assertEqual(self.state[1],50)
    def test_door_toggle_travel_and_close(self):
        self.lib.pose(0,500);self.update(64)
        self.assertEqual(self.state[3],48)
        for _ in range(20):self.update(64)
        self.assertEqual(self.state[3],600)
        self.update();self.update(64)
        for _ in range(20):self.update()
        self.assertEqual(self.state[3],0)
    def test_closed_door_blocks_movement_and_open_door_allows_it(self):
        self.lib.pose(0,700)
        for _ in range(10):self.update(4)
        closed=self.player.z;self.assertLess(closed,800)
        self.update(64)
        for _ in range(16):self.update()
        for _ in range(12):self.update(4)
        self.assertGreater(self.player.z,1000)
    def test_enemy_uses_eight_original_frames(self):
        seen={self.state[6]}
        for _ in range(40):self.update();seen.add(self.state[6])
        self.assertEqual(seen,set(range(8)))
    def test_hud_and_animation_submit_existing_gpu_commands(self):
        tri=self.lib.counter(0);uploads=self.lib.counter(1)
        self.assertEqual(self.lib.game_port_render(1),0)
        self.assertGreater(self.lib.counter(0)-tri,40);self.assertGreater(self.lib.counter(1),uploads)
        same=self.lib.counter(1);self.assertEqual(self.lib.game_port_render(2),0);self.assertEqual(self.lib.counter(1),same)
        for _ in range(4):self.update()
        self.assertEqual(self.lib.game_port_render(3),0);self.assertGreater(self.lib.counter(1),same)
    def test_enemy_contact_damage_and_armor_absorption(self):
        self.lib.pose(0,600);self.update();self.lib.pose(324,1440);self.update()
        self.assertEqual((self.state[0],self.state[1]),(95,45))
    def test_hud_uses_legal_frame_commands_and_stays_beyond_near_plane(self):
        for yaw in range(0,256,32):
            for pitch in (-32,0,32):
                self.update(yaw=yaw,pitch=pitch)
                self.assertEqual(self.lib.game_port_render(1),0)
                self.assertGreaterEqual(self.lib.counter(3),257)
    def test_hitscan_ammo_cooldown_and_enemy_defeat(self):
        self.lib.pose(320,900)
        for _ in range(13):
            x=self.lib.enemy_axis(0)-self.player.x;y=self.lib.enemy_axis(1)-self.player.y-184;z=self.lib.enemy_axis(2)-self.player.z
            yaw=round(math.atan2(x,z)*256/math.tau)&255
            pitch=round(math.atan2(y,math.hypot(x,z))*256/math.tau)
            self.update(32,yaw,pitch)
        self.assertEqual((self.state[2],self.state[5]),(17,0))
    def test_original_topology_and_animation_mapping_preserved(self):
        entries=quake_assets.pak_entries((ROOT/'build/quake-shareware/pak0.pak').read_bytes())
        palette=quake_assets.records(entries['gfx/palette.lmp'],'<3B')
        frames,tris,report=quake_demo.mdl(entries['progs/soldier.mdl'],palette,'run')
        self.assertEqual((len(frames),len(tris),report['vertices']),(8,328,170))
        scene=json.loads((ROOT/'build/quake-interactive/scene.json').read_text())
        actor=next(m for m in scene['meshes'] if m['id']=='enemy')
        self.assertEqual(actor['vertices'],frames[0][1]);self.assertEqual(actor['triangles'],tris)
        compiled=portable_game.compile_scene(scene,False);self.assertEqual(compiled[-1]['world_triangles'],786)
        self.assertEqual(compiled[-1]['actor_triangles'],438)
    def test_linked_package_and_capabilities(self):
        path=ROOT/'build/quake-interactive-sdram.package.json';spec=json.loads(path.read_text())
        self.assertEqual(spec['target']['id'],'de2-115-fixed-v2');self.assertIn('mouse-look-v1',spec['target']['required_features'])
        self.assertEqual(len(load_game.package_segments(path)),2)
    def test_old_hardware_is_rejected_without_holding_cpu(self):
        class OldHardware:
            retries=8
            def operation(self,op,**kwargs):
                self.last=op;return {'input_abi':0}
        old=OldHardware();spec={'target':{'required_features':['mouse-look-v1']}}
        with self.assertRaisesRegex(RuntimeError,'CPU left running'):load_game.require_hardware(old,spec)
        self.assertEqual(old.last,load_game.STATUS)
    def test_degenerate_actor_retention_is_explicit_and_preserves_faces(self):
        scene=json.loads((ROOT/'build/quake-interactive/scene.json').read_text())
        compiled=portable_game.compile_scene(scene,False)
        self.assertGreater(compiled[-1]['explicitly_retained_degenerate_actor_faces'],0)
        scene['meshes'][0]['retain_degenerate_actor_faces']=True
        with self.assertRaisesRegex(ValueError,'Only actor'):portable_game.compile_scene(scene,False)

if __name__=='__main__':unittest.main()
