"""Exercise independent gameplay, shared runtime and package compatibility."""
import copy
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import game_package
import load_game
from test_player import Player, world_for

ROOT=Path(__file__).resolve().parents[1]
class State(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('collected','score','ticks','respawns','won')]
class Config(c.Structure):
    _fields_=[('positions',c.POINTER(c.c_int16*3)),('count',c.c_uint32),('radius',c.c_int32),('height',c.c_int32)]

class PackagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=game_package.generate(ROOT/'profiles/beacon-run.json')
        cls.profile=json.loads((ROOT/'profiles/beacon-run.json').read_text())
        out=ROOT/'build/package-tests'; out.mkdir(parents=True,exist_ok=True)
        (out/'soc.h').write_text('''#include <stdint.h>
extern uint32_t runtime_cycles,runtime_buttons;
#define SOC_CYCLES runtime_cycles
#define SOC_BUTTONS runtime_buttons
int gfx_wait_frame(uint32_t frame);
''')
        fixture=out/'fixture.c'
        fixture.write_text('''#include "game_runtime.h"
#include "beacon_data.h"
#include "gfx.h"
uint32_t runtime_cycles,runtime_buttons;
static uint32_t writes, definitions, indices, vertices, fail_at, completed;
static int emit(void) { ++writes; return writes==fail_at ? -1 : 0; }
int gfx_palette(uint8_t i,uint8_t r,uint8_t g,uint8_t b) { (void)i;(void)r;(void)g;(void)b;return emit(); }
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t) { (void)h;(void)v;(void)t;++definitions;return emit(); }
int gfx_vertex(uint8_t h,uint8_t i,int16_t x,int16_t y,int16_t z) { (void)h;(void)i;(void)x;(void)y;(void)z;++vertices;return emit(); }
int gfx_index(uint8_t h,uint16_t i,uint8_t a,uint8_t b,uint8_t cc,uint8_t color) { (void)h;(void)i;(void)a;(void)b;(void)cc;(void)color;++indices;return emit(); }
int gfx_wait_frame(uint32_t frame) { completed=frame;return 0; }
int upload(unsigned mode) {
 game_asset_set_t assets={GAME_RUNTIME_ABI,world_meshes,actor_meshes,3,2,game_palette,GAME_PALETTE_COUNT};
 writes=definitions=vertices=indices=0;fail_at=mode==3?4:0;
 if(mode==1) assets.abi_version=2;
 if(mode==2) assets.actor_count=14;
 return game_runtime_upload(&assets,0,mode==4?1:0);
}
unsigned upload_stat(unsigned index) { return index==0?writes:index==1?definitions:index==2?vertices:indices; }
unsigned clock_fixture(unsigned previous,unsigned now,unsigned period) {
 game_runtime_clock_t clock;runtime_cycles=previous;game_runtime_clock_reset(&clock,period);
 runtime_cycles=now; unsigned captured=game_runtime_wait_tick(&clock);
 do {} while(game_runtime_advance_tick(&clock,captured));
 return clock.ticks;
}
unsigned input_fixture(unsigned buttons) { runtime_buttons=buttons;return game_runtime_input(); }
unsigned present_fixture(unsigned frame) { game_runtime_present(frame);return completed; }
''')
        exports=('beacon_reset','beacon_step','player_reset','player_step','upload','upload_stat','clock_fixture','input_fixture','present_fixture')
        flags=['-shared','-O1','-Wall','-Wextra','-Werror','-I'+str(out),
               '-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated')]
        dll=out/('packages.dll' if os.name=='nt' else 'packages.so')
        if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+name for name in exports]
        else:flags+=['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(fixture),str(ROOT/'firmware/src/beacon.c'),
            str(ROOT/'firmware/src/player.c'),str(ROOT/'firmware/src/game_runtime.c'),'-o',str(dll)],check=True)
        cls.lib=c.CDLL(str(dll))
        cls.lib.beacon_reset.argtypes=[c.POINTER(State),c.POINTER(Player)]
        cls.lib.beacon_step.argtypes=[c.POINTER(State),c.POINTER(Player),c.POINTER(Config)]
        cls.lib.player_reset.argtypes=[c.POINTER(Player),c.c_void_p]
        cls.lib.player_step.argtypes=[c.POINTER(Player),c.c_void_p,c.c_uint32]
        cls.lib.clock_fixture.argtypes=[c.c_uint32]*3;cls.lib.clock_fixture.restype=c.c_uint32

    def fixture(self):
        chunks=[game_package.mesh(x,len(self.profile['palette'])) for x in self.profile['world']]
        world=world_for(chunks,self.profile['spawn'])
        for key,value in self.profile['physics'].items():setattr(world,key,value)
        player=Player(); self.lib.player_reset(c.byref(player),c.byref(world))
        points=(c.c_int16*3*3)(*( (c.c_int16*3)(*p) for p in self.profile['game']['beacons']))
        config=Config(points,3,96,80);state=State();self.lib.beacon_reset(c.byref(state),c.byref(player))
        return world,player,state,config,points

    def test_collect_once_height_gate_win_and_respawn(self):
        world,p,s,cfg,points=self.fixture()
        for i,point in enumerate(points):
            p.x,p.y,p.z=point[0],point[1]+81,point[2]
            self.lib.beacon_step(c.byref(s),c.byref(p),c.byref(cfg));self.assertEqual(s.score,i)
            p.y=point[1]
            for _ in range(3):self.lib.beacon_step(c.byref(s),c.byref(p),c.byref(cfg))
            self.assertEqual(s.score,i+1)
        self.assertEqual((s.won,s.collected),(1,7))
        ticks=s.ticks; self.lib.beacon_step(c.byref(s),c.byref(p),c.byref(cfg));self.assertEqual(s.ticks,ticks)
        self.lib.player_step(c.byref(p),c.byref(world),15)
        self.lib.beacon_step(c.byref(s),c.byref(p),c.byref(cfg));self.assertEqual((s.score,s.won,s.collected),(0,0,0))

    def test_production_controller_route_needs_jumps(self):
        world,p,s,cfg,_=self.fixture()
        def step(keys):
            self.lib.player_step(c.byref(p),c.byref(world),keys)
            self.lib.beacon_step(c.byref(s),c.byref(p),c.byref(cfg))
        def walk(x,z,limit=100):
            for _ in range(limit):
                dx,dz=x-p.x,z-p.z
                if abs(dx)<=16 and abs(dz)<=16:return
                step((2 if dx>16 else 1 if dx<-16 else 0)|(4 if dz>16 else 8 if dz<-16 else 0))
            self.fail(f'Blocked route at {(p.x,p.y,p.z)}, target {(x,z)}')
        walk(-384,-192);self.assertEqual(s.score,1)
        walk(-384,160);walk(-256,160)
        for _ in range(15):step(2)
        self.assertLess(p.x,-192);self.assertEqual(s.score,1)
        # Retreat to jump distance, then clear the first platform wall.
        walk(-256,160);step(18)
        for _ in range(13):step(2)
        walk(0,160)
        for _ in range(15):step(0)
        self.assertEqual((p.y,p.grounded,s.score),(64,1,2))
        walk(144,320);step(18)
        for _ in range(13):step(2)
        walk(480,400)
        for _ in range(15):step(0)
        self.assertEqual((p.y,p.grounded,s.score,s.won),(128,1,3,1))

    def test_shared_upload_capacity_and_backpressure_failure(self):
        self.assertEqual(self.lib.upload(0),0)
        self.assertEqual([self.lib.upload_stat(i) for i in (1,2,3)],[5,34,46])
        for mode in (1,2,4):
            self.assertEqual(self.lib.upload(mode),-1);self.assertEqual(self.lib.upload_stat(0),0)
        self.assertEqual(self.lib.upload(3),-1);self.assertEqual(self.lib.upload_stat(0),4)

    def test_runtime_clock_wrap_catchup_input_and_frame_identity(self):
        self.assertEqual(self.lib.clock_fixture(0xfffffff0,0x20,32),1)
        self.assertEqual(self.lib.clock_fixture(100,199,32),3)
        self.assertEqual(self.lib.clock_fixture(100,10000,32),4)
        self.assertEqual(self.lib.input_fixture(18),18)
        self.assertEqual(self.lib.present_fixture(42),42)

    def test_schema_and_capacity_rejection(self):
        game_package.validate_content(self.content)
        for key,value in (('version',2),('runtime_abi',2),('palette_colors',257),('material_policy','texture')):
            bad=copy.deepcopy(self.content);bad[key]=value
            with self.assertRaises(ValueError):game_package.validate_content(bad)
        bad=copy.deepcopy(self.content);bad['meshes'][0]['vertices']=129
        with self.assertRaises(ValueError):game_package.validate_content(bad)

    def test_both_linked_packages_have_distinct_games_shared_abi(self):
        paths=[ROOT/'build'/name for name in ('mario-sdram.package.json','quake-sdram.package.json')]
        specs=[json.loads(path.read_text()) for path in paths]
        for path,spec in zip(paths,specs):
            self.assertEqual(spec['content']['runtime_abi'],1);self.assertEqual(len(load_game.package_segments(path)),2)
        self.assertNotEqual(specs[0]['content']['game'],specs[1]['content']['game'])
        self.assertNotEqual(specs[0]['segments'][1]['sha256'],specs[1]['segments'][1]['sha256'])
        self.assertEqual(specs[0]['content']['animation']['abi'],'indexed-joints-q14-v1')
        self.assertEqual(specs[1]['content']['animation']['abi'],'none')

if __name__=='__main__':unittest.main()
