"""Compare production fixed-point skeletal poses with original source channels."""
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import animation_assets as assets
from test_player import Player

ROOT=Path(__file__).resolve().parents[1]
class Vertex(c.Structure):
    _fields_=[(k,c.c_int16) for k in ('x','y','z')]
class Matrix(c.Structure):
    _fields_=[('r',c.c_int16*9),('t',c.c_int32*3)]
class State(c.Structure):
    _fields_=[(k,c.c_uint32) for k in ('clip','phase','grounded','respawns')]+[
        ('previous_x',c.c_int32),('previous_z',c.c_int32)]

class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile=json.loads((ROOT/'profiles/sm64-mario.json').read_text())
        cls.joints,cls.display,cls.clips,_=assets.load(ROOT/'external/sm64',profile['animation'])
        cls.report=json.loads((ROOT/'build/game/conversion.json').read_text())['animation']
        cls.count=len(cls.report['vertex_sources'])
        out=ROOT/'build/animation-tests';out.mkdir(parents=True,exist_ok=True)
        wrapper=out/'fixture.c'
        wrapper.write_text('''#include "game_data.h"
void pose_fixture(unsigned clip,unsigned frame,unsigned grounded,scene_vertex_t *out,animation_matrix_t *matrices) {
 animation_t state={clip,frame<<8,grounded,0,0,0};
 animation_pose(&state,&game_animation_package,matrices,out);
}
void reset_fixture(animation_t *state,const player_t *player) { animation_reset(state,player,&game_animation_package); }
void step_fixture(animation_t *state,const player_t *player) { animation_step(state,player,&game_animation_package); }
void source_fixture(scene_vertex_t *out) {
 unsigned index=0;
 for(unsigned i=0;i<game_animation_package.mesh_count;++i)
  for(unsigned v=0;v<actor_meshes[i].vertex_count;++v,++index) {
   out[index].x=actor_meshes[i].vertices[v].x;
   out[index].y=actor_meshes[i].vertices[v].y;
   out[index].z=actor_meshes[i].vertices[v].z;
  }
}
''')
        flags=['-shared','-O1','-Wall','-Wextra','-Werror',
               '-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated')]
        dll=out/('animation.dll' if os.name=='nt' else 'animation.so')
        if os.name=='nt':flags += ['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+[
            '-Wl,/export:'+s for s in ('pose_fixture','reset_fixture','step_fixture','source_fixture')]
        else:flags += ['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(wrapper),str(ROOT/'firmware/src/animation.c'),
                        str(ROOT/'firmware/src/player.c'),'-o',str(dll)],check=True)
        cls.lib=c.CDLL(str(dll))
        cls.lib.pose_fixture.argtypes=[c.c_uint32,c.c_uint32,c.c_uint32,c.POINTER(Vertex),c.POINTER(Matrix)]
        cls.lib.source_fixture.argtypes=[c.POINTER(Vertex)]
        for name in ('reset_fixture','step_fixture'):
            getattr(cls.lib,name).argtypes=[c.POINTER(State),c.POINTER(Player)]

    def pose(self,clip,frame,grounded):
        vertices=(Vertex*self.count)();matrices=(Matrix*len(self.joints))()
        self.lib.pose_fixture(clip,frame,grounded,vertices,matrices)
        return [(v.x,v.y,v.z) for v in vertices],matrices

    def reference(self,clip,frame,grounded):
        matrices=assets.pose(self.joints,self.clips[clip],frame)
        r=self.report;scale=r['scale_q14']/16384;base=r['base_y_q4']/16
        values=[]
        for vertex in r['vertex_sources']:
            x,y,z=assets.vertex(matrices[vertex['joint']],vertex['local'])
            values.append((x*scale,(y-base)*scale,z*scale))
        if grounded:
            sole=min(p[1] for p,v in zip(values,r['vertex_sources']) if r['foot_joints']&(1<<v['joint']))
            values=[(x,y-sole,z) for x,y,z in values]
        return values,matrices

    def test_source_local_vertices_are_unchanged(self):
        vertices=(Vertex*self.count)();self.lib.source_fixture(vertices)
        self.assertEqual([(v.x,v.y,v.z) for v in vertices],[tuple(v['local']) for v in self.report['vertex_sources']])
        self.assertEqual(len(self.joints),20)
        self.assertEqual(len(self.display),15)
        self.assertEqual([j['parent'] for j in self.joints],[-1,0,1,2,2,4,5,6,2,8,9,10,1,12,13,14,1,16,17,18])

    def test_all_original_frames_match_independent_float_poses(self):
        worst=0
        for i,clip in enumerate(self.clips):
            for frame in range(clip['start'],clip['end']):
                for grounded in (0,1):
                    actual,matrix=self.pose(i,frame,grounded);expected,ref=self.reference(i,frame,grounded)
                    error=max(abs(a-b) for p,q in zip(actual,expected) for a,b in zip(p,q))
                    worst=max(worst,error)
                    self.assertLess(error,2.1,(clip['symbol'],frame,grounded,error))
                    for native,(rotation,translation) in zip(matrix,ref):
                        self.assertLess(max(abs(native.r[3*a+b]/16384-rotation[a][b]) for a in range(3) for b in range(3)),.001)
                        self.assertLess(max(abs(native.t[k]/16-translation[k]) for k in range(3)),.5)
        print('Maximum skeletal vertex error:',round(worst,4),'Q8.8 coordinate units')

    def test_original_channels_preserved_at_every_reachable_frame(self):
        for clip in self.clips:
            for channel,(count,index) in enumerate(zip(clip['source_indices'][::2],clip['source_indices'][1::2])):
                samples=clip['channels'][channel]
                for frame in range(clip['start'],clip['end']):
                    self.assertEqual(samples[min(frame-clip['start'],len(samples)-1)],
                                     clip['raw_values'][index+min(frame,count-1)])

    def test_grounded_foot_contact_and_airborne_pose_are_separate(self):
        r=self.report
        for i in (0,1,3):
            clip=self.clips[i]
            for frame in range(clip['start'],clip['end']):
                vertices,_=self.pose(i,frame,1)
                self.assertEqual(min(p[1] for p,v in zip(vertices,r['vertex_sources']) if r['foot_joints']&(1<<v['joint'])),0)
        air,_=self.pose(2,8,0);ground,_=self.pose(2,8,1)
        shifts={b[1]-a[1] for a,b in zip(air,ground)}
        self.assertEqual(len(shifts),1)
        self.assertTrue(all(a[0]==b[0] and a[2]==b[2] for a,b in zip(air,ground)))

    def test_original_xyz_axes_and_neutral_root(self):
        for angle,expected in (([0,0,16384],[[0,-1,0],[1,0,0],[0,0,1]]),
                               ([0,16384,0],[[0,0,1],[0,1,0],[-1,0,0]])):
            actual=assets.rotation(angle)
            self.assertLess(max(abs(actual[a][b]-expected[a][b]) for a in range(3) for b in range(3)),1e-10)
        vertices,matrices=self.pose(0,0,1)
        self.assertEqual(tuple(matrices[0].t),(0,171*16,0))
        self.assertGreater(max(v[1] for v in vertices),124)
        self.assertLess(max(v[1] for v in vertices),132)

    def test_state_transitions_idle_walk_jump_land_respawn(self):
        p=Player();p.grounded=1;s=State()
        self.lib.reset_fixture(c.byref(s),c.byref(p));self.assertEqual(s.clip,0)
        p.x=8;self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual((s.clip,s.phase),(1,0))
        p.x=16;self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual(s.phase,512)
        self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual(s.clip,0) # blocked/stopped
        p.grounded=0;self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual(s.clip,2)
        for _ in range(20):self.lib.step_fixture(c.byref(s),c.byref(p))
        self.assertEqual(s.phase,11<<8)
        p.grounded=1;self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual((s.clip,s.phase),(3,22<<8))
        for _ in range(16):self.lib.step_fixture(c.byref(s),c.byref(p))
        self.assertEqual(s.clip,0)
        p.respawns+=1;p.x=100;self.lib.step_fixture(c.byref(s),c.byref(p));self.assertEqual((s.clip,s.phase,s.previous_x),(0,0,100))

    def test_animation_does_not_modify_player_or_add_lateral_motion(self):
        p=Player();p.grounded=0;p.x=125;p.z=-63;p.y=200;s=State()
        self.lib.reset_fixture(c.byref(s),c.byref(p));before=bytes(p)
        for _ in range(30):self.lib.step_fixture(c.byref(s),c.byref(p))
        self.assertEqual(bytes(p),before)
        for i,clip in enumerate(self.clips):
            _,m=self.pose(i,clip['end']-1,0)
            self.assertEqual((m[0].t[0],m[0].t[2]),(0,0))

    def test_source_policies_reject_unresolved_or_unsupported_nodes(self):
        p=json.loads((ROOT/'profiles/sm64-mario.json').read_text())['animation']
        for changed in ({'geo_root':'missing'},{'neutral_callbacks':[]},{'omit_static_alpha':[]},
                        {'switch_choices':{'geo_switch_mario_cap_on_off':100}},{'geo_source':'../escape.c'}):
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                assets.hierarchy(ROOT/'external/sm64',{**p,**changed})

if __name__=='__main__':unittest.main(verbosity=2)
