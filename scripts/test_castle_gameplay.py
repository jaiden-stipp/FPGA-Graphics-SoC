"""Native production gameplay checks on pinned, complete castle collision data.

Direct placement tests isolate mission/warp contracts. They are not a claim
that a human completed the complete level on the FPGA.
"""
import ctypes as c
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import sm64_castle
import sm64_gameplay
import portable_game

ROOT=Path(__file__).resolve().parents[1]
NATIVE=r'''
#include "castle_game.c"
#include "gfx_protocol.h"
uint32_t test_registers[64];
static int active,errors,commands,door_triangles;
int gfx_identity_view(void){if(active)++errors;return 0;}
int gfx_begin_frame(uint32_t frame){(void)frame;if(active)++errors;active=1;return 0;}
int gfx_end_frame(void){if(!active)++errors;active=0;return 0;}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t){(void)h;(void)v;(void)t;if(active)++errors;return 0;}
int gfx_draw_matrix(uint8_t h,const int16_t v[12]){(void)h;(void)v;if(!active)++errors;++commands;return 0;}
int gfx_command(uint8_t op,const uint8_t *bytes,uint8_t n){if(op==GFX_OP_DRAW_TRIANGLE && !active)++errors;if(op==GFX_OP_DRAW_TRIANGLE && n==19 && (int16_t)((uint16_t)bytes[4]<<8|bytes[5])>300)++door_triangles;++commands;return 0;}
void test_init(void){active=errors=commands=0;game_port_init();}
void test_place(uint32_t area,int32_t x,int32_t y,int32_t z){int16_t arrival[3]={(int16_t)x,(int16_t)y,(int16_t)z};enter_area(area,arrival,0);camera_update();render_capture(1);}
void test_position(int32_t x,int32_t y,int32_t z){player.x=x;player.y=y;player.z=z;player.velocity_y=0;player.grounded=0;}
void test_input(uint32_t word){game_port_update(word);}
int32_t test_state(uint32_t field){switch(field){case 0:return player.x;case 1:return player.y;case 2:return player.z;case 3:return (int32_t)current_area;case 4:return (int32_t)player.grounded;case 5:return (int32_t)controller.action;case 6:return (int32_t)player.respawns;case 7:return (int32_t)pending_event;case 8:return errors;case 9:return commands;default:return -1;}}
int test_render(void){return game_port_render(1);}
int test_door_view(uint32_t area,int32_t x,int32_t y,int32_t z){player_t p={0};p.x=x;p.y=y;p.z=z-600;game_view_t v={0,0,{256,0,0,0,0,256,0,-128,0,0,256,0}};door_triangles=0;gfx_begin_frame(1);int result=castle_gameplay_draw(area,&p,&v);gfx_end_frame();return result? -1:door_triangles;}
int32_t test_floor(uint32_t area,int32_t x,int32_t z,int32_t ceiling){player_t p={0};p.x=x;p.z=z;p.y=ceiling;world_collision(world_areas+area,&p);return player_floor(world_areas[area].physics,x,z,ceiling);}
'''

class CastleGameplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=ROOT/'build/castle-gameplay-tests';cls.folder.mkdir(parents=True,exist_ok=True)
        cls.world=sm64_castle.export(cls.folder,gameplay=True)
        spec,_,_,sources,_,_=portable_game.generate(cls.folder/'game.project.json')
        shim=cls.folder/'native_mmio.h';shim.write_text('#include <stdint.h>\nextern uint32_t test_registers[64];\n#define SOC_REG(offset) test_registers[(offset)/4]\n',encoding='utf-8')
        wrapper=cls.folder/'native.c';wrapper.write_text(NATIVE,encoding='utf-8')
        dll=cls.folder/('gameplay.dll' if os.name=='nt' else 'gameplay.so')
        flags=['-shared','-O1','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin',
            '-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated'),'-I'+str(ROOT/'firmware/ports'),'-include',str(shim)]
        names=['test_init','test_place','test_position','test_input','test_state','test_render','test_floor','castle_gameplay_probe','test_door_view']
        if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+n for n in names]
        else:flags+=['-fPIC']
        files=[wrapper,ROOT/'firmware/src/player.c',ROOT/'firmware/src/portable_assets.c']+[s for s in sources if s.name!='castle_game.c']
        subprocess.run([shutil.which('clang'),*flags,*map(str,files),'-o',str(dll)],check=True,capture_output=True,text=True)
        cls.lib=c.CDLL(str(dll));cls.lib.test_state.restype=cls.lib.test_floor.restype=cls.lib.castle_gameplay_probe.restype=c.c_int32
    def setUp(self):self.lib.test_init()
    def state(self,n):return self.lib.test_state(n)
    def probe(self,n):return self.lib.castle_gameplay_probe(n)
    def tick(self,word=0,count=1):
        for _ in range(count):self.lib.test_input(word)
    def test_source_behaviors_have_provenance(self):
        report=json.loads((self.folder/'gameplay-coverage.json').read_text())
        self.assertEqual(len(report['imported_functions']),9)
        self.assertEqual(report['mission_source']['box_position'],[-6385,-4200,5770])
        self.assertIn('not complete SM64 action engine',report['limitations'])
    def test_all_five_areas_land_on_original_collision(self):
        for area,a in enumerate(self.world['areas']):
            self.lib.test_place(area,*a['spawn']);self.tick(count=80)
            self.assertEqual(self.state(3),area);self.assertEqual(self.state(4),1)
    def test_jump_ground_pound_and_landing(self):
        self.lib.test_place(1,-1023,0,1152);self.tick(count=10)
        floor=self.state(1);self.tick(16);self.assertGreater(self.state(1),floor)
        self.tick(64);self.assertEqual(self.state(5),4)
        self.tick(count=30);self.assertEqual(self.state(4),1)
    def test_original_box_top_is_solid(self):
        self.lib.test_place(4,-6385,-4096,5770);self.tick(count=15)
        self.assertEqual(self.state(1),-4096);self.assertEqual(self.state(4),1)
        self.assertEqual(self.probe(0),2);self.assertNotEqual(self.probe(1),0)
        self.tick(16);self.assertGreater(self.state(1),-4096);self.assertEqual(self.state(4),0)
    def test_doors_and_original_area_transition(self):
        t=next(t for t in self.world['transitions'] if t['source_area']==1 and t['destination_area']==2)
        self.lib.test_place(1,*t['position']);self.tick(count=16);self.tick(64)
        self.assertEqual(self.state(3),2)
    def test_front_entrance_submits_visible_door_geometry(self):
        self.assertGreater(self.lib.test_door_view(0,0,803,-3155),0)
    def test_source_warp_door_inventory_and_material_separation(self):
        rows=sm64_gameplay.warp_doors(sm64_castle.sm64_subset.fetch(),self.world)
        report=json.loads((self.folder/'gameplay-coverage.json').read_text())
        self.assertEqual(report['warp_doors'],rows)
        self.assertIn([0,-76,803,-3155,0,1],rows)
        self.assertIn([1,-1100,512,-1074,0,1],rows)
        for name in ('door','castle_door','metal_door'):
            model=next(m for m in report['models'] if m['id']==name)
            self.assertGreaterEqual(len(model['used_palette_indices']),3)
            self.assertEqual(model['source_scale'],0.25)
            self.assertEqual(model['geo_translation'],[3,0,0])
    def test_camera_facing_movement_preserves_collision(self):
        self.lib.test_place(0,-1328,260,4664);self.tick(count=30)
        before=self.state(2);self.tick(4,count=60)
        self.assertGreater(self.state(2),before);self.assertEqual(self.state(6),0)
    def test_slide_slope_accelerates_without_keys(self):
        # A source floor centroid; downhill acceleration is derived from its
        # original normal, not from the rendered triangle palette.
        a=self.world['areas'][4];v=a['collision']['vertices']
        candidates=[]
        for tri in a['collision']['triangles']:
            p,q,r=(v[i] for i in tri[:3]);u=[q[i]-p[i] for i in range(3)];w=[r[i]-p[i] for i in range(3)]
            n=[u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]]
            if n[1]>0 and n[0]*n[0]+n[2]*n[2]>n[1]*n[1]//25 and min(p[1],q[1],r[1])>0:candidates.append((p,q,r))
        self.assertTrue(candidates)
        p,q,r=candidates[0];x=sum(k[0] for k in (p,q,r))//3;z=sum(k[2] for k in (p,q,r))//3
        y=self.lib.test_floor(4,x,z,15000);self.lib.test_place(4,x,y,z);self.tick(count=20)
        self.assertNotEqual((self.state(0),self.state(2)),(x,z));self.assertEqual(self.state(6),0)
    def test_complete_slide_with_controls_and_no_position_injection(self):
        self.lib.test_place(4,5632,6451,-5631)
        # Source coin/sign-line centers guide the replay. The last two points
        # are authored approaches to the original star-box position. This is
        # a test driver, not an autopilot shipped in game code.
        points=[[-3233,-5600],[-5636,-5054],[-5980,945],[-2870,2300],[3930,2425],
            [5174,3200],[5707,4565],[5194,5845],[3640,6450],[2550,6050],[1821,4616],
            [1860,1680],[1880,60],[1860,-1720],[1854,-4290],[-20,-6304],[-1197,-4692],
            [-2565,-3525],[-4909,-4218],[-6290,-2545],[-6400,-590],[-6400,1409],
            [-6400,3481],[-6385,5600],[-6385,5770]]
        index=0;trace=[]
        for tick in range(1800):
            x,y,z=[self.state(k) for k in range(3)];distance=math.hypot(x-points[index][0],z-points[index][1])
            if index+1<len(points) and distance<(500 if index<22 else 140):index+=1
            yaw=round(math.atan2(points[index][0]-x,points[index][1]-z)*128/math.pi)&255
            word=0x80000000|(yaw<<8)|4
            if index>=23 and tick%45==0:word|=16
            if index==24 and distance<100:word=16 if tick%45==0 else 0
            self.tick(word)
            trace.append({'tick':tick,'input':word,'target':index,'position':[x,y,z],
                          'area':self.state(3),'mission':self.probe(7),'respawns':self.state(6)})
            if self.state(3)!=4:break
        (self.folder/'full-slide-inputs.json').write_text(json.dumps(trace,indent=2)+'\n',encoding='utf-8')
        self.assertEqual(self.probe(7),1);self.assertEqual(self.state(3),1);self.assertEqual(self.state(6),0)
    def test_box_star_spawn_collect_exit_and_save_once(self):
        # Start on the actual original floor, then use one jump. No position
        # injection is used to open the box or collect the spawned star.
        y=self.lib.test_floor(4,-6385,5770,-4100)
        self.lib.test_place(4,-6385,y,5770);self.tick(count=5);self.tick(16)
        seen_box=seen_star=seen_exit=False
        for _ in range(200):
            self.tick();seen_box|=self.probe(0)==3;seen_star|=self.probe(3)!=0;seen_exit|=self.state(7)==240
        self.assertTrue(seen_box and seen_star and seen_exit)
        self.assertEqual(self.state(3),1);self.assertEqual(self.probe(7),1)
        # Save is preserved across area transitions and repeat mission entry.
        self.lib.test_place(4,5632,6451,-5631);self.assertEqual(self.probe(7),1)
    def test_repeat_render_does_not_advance_mission(self):
        self.lib.test_place(4,-6385,-4280,5770);self.tick(count=3)
        before=[self.probe(i) for i in range(9)];position=[self.state(i) for i in range(7)]
        for _ in range(3):self.assertEqual(self.lib.test_render(),0)
        self.assertEqual([self.probe(i) for i in range(9)],before)
        self.assertEqual([self.state(i) for i in range(7)],position);self.assertEqual(self.state(8),0);self.assertGreater(self.state(9),0)
    def test_display_list_tail_call_does_not_return(self):
        text='const Vtx v[]={{{{0,0,0},0,{0,0},{0,0,0,0}}},{{{1,0,0},0,{0,0},{0,0,0,0}}},{{{0,1,0},0,{0,0},{0,0,0,0}}}};const Gfx child[]={gsSPVertex(v,3,0),gsSP1Triangle(0,1,2,0),gsSPEndDisplayList()};const Gfx root[]={gsSPBranchList(child),gsSP1Triangle(0,1,2,0),gsSPEndDisplayList()};'
        import sm64_subset
        _,faces,_,_=sm64_subset.lower(text,{'display_list':'root','discard_state':[]})
        self.assertEqual(len(faces),1)
if __name__=='__main__':unittest.main()
