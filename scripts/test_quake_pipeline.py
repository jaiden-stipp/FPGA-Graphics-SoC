"""Check original BSP provenance and production first-person collision/view code."""
import ctypes as c
import copy
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import quake_assets
from test_player import Player

ROOT=Path(__file__).resolve().parents[1]
class Camera(c.Structure):
    _fields_=[('yaw',c.c_uint32),('respawns',c.c_uint32),('view',c.c_int16*12)]

class QuakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=json.loads((ROOT/'profiles/quake-e1m1.json').read_text())
        cls.chunks,_,_,_,cls.report=quake_assets.prepare(ROOT/'build/quake-shareware/pak0.pak',cls.profile)
        directory=ROOT/'build/quake-tests'; directory.mkdir(parents=True,exist_ok=True)
        wrapper=directory/'fixture.c'
        wrapper.write_text('''#include "quake_data.h"
void reset_fixture(player_t *p,first_person_t *c) { player_reset(p,&game_world);first_person_reset(c,p,&game_first_person); }
void step_fixture(player_t *p,first_person_t *c,unsigned keys) { first_person_step(c,p,&game_world,&game_first_person,keys); }
int floor_fixture(int x,int z,int ceiling) { return player_floor(&game_world,x,z,ceiling); }
''')
        dll=directory/('quake.dll' if os.name=='nt' else 'quake.so')
        flags=['-shared','-O1','-Wall','-Wextra','-Werror','-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated')]
        if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+name for name in ('reset_fixture','step_fixture','floor_fixture')]
        else:flags+=['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(wrapper),str(ROOT/'firmware/src/first_person.c'),str(ROOT/'firmware/src/player.c'),'-o',str(dll)],check=True)
        cls.lib=c.CDLL(str(dll)); cls.lib.reset_fixture.argtypes=[c.POINTER(Player),c.POINTER(Camera)]
        cls.lib.step_fixture.argtypes=[c.POINTER(Player),c.POINTER(Camera),c.c_uint32]
        cls.lib.floor_fixture.argtypes=[c.c_int32]*3; cls.lib.floor_fixture.restype=c.c_int32

    def start(self):
        player=Player();camera=Camera();self.lib.reset_fixture(c.byref(player),c.byref(camera));return player,camera
    def step(self,p,camera,keys=0,count=1):
        for _ in range(count):self.lib.step_fixture(c.byref(p),c.byref(camera),keys)

    def test_bsp_faces_keep_original_vertices_and_topology(self):
        entries=quake_assets.pak_entries((ROOT/'build/quake-shareware/pak0.pak').read_bytes())
        lumps=quake_assets.bsp_lumps(entries[self.profile['map']])
        vertices=list(struct.iter_unpack('<3f',lumps[3])); planes=list(struct.iter_unpack('<4fi',lumps[1]))
        faces=list(struct.iter_unpack('<hhihh4Bi',lumps[7]));edges=list(struct.iter_unpack('<2H',lumps[12]))
        surfedges=[x[0] for x in struct.iter_unpack('<i',lumps[13])]
        count=0
        for (points,triangles),mapping in zip(self.chunks,self.report['chunk_source_triangles']):
            self.assertLessEqual(len(points),128);self.assertLessEqual(len(triangles),256)
            for triangle,record in zip(triangles,mapping):
                face=faces[record['face']]; polygon=[]
                for edge in surfedges[face[2]:face[2]+face[3]]:polygon.append(edges[abs(edge)][0 if edge>=0 else 1])
                self.assertIn(record['vertices'][0],polygon)
                self.assertTrue(all(v in polygon for v in record['vertices']))
                for index,source_id in zip(triangle[:3],record['vertices']):
                    source=vertices[source_id]; origin=self.report['source_origin']
                    expected=tuple(round((source[a]-origin[a])*self.profile['scale']) for a in (0,2,1))
                    self.assertEqual(points[index],expected)
                pts=[points[i] for i in triangle[:3]]
                u=[pts[1][i]-pts[0][i] for i in range(3)];v=[pts[2][i]-pts[0][i] for i in range(3)]
                n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
                normal=planes[face[0]]; target=[normal[a]*(-1 if face[1] else 1) for a in (0,2,1)]
                self.assertGreater(sum(n[i]*target[i] for i in range(3)),0)
                count+=1
        self.assertEqual((count,len(self.chunks)),(786,5))

    def test_original_spawn_and_camera_all_yaws(self):
        p,camera=self.start();self.assertEqual((p.x,p.y,p.z,p.grounded),(0,0,0,1))
        self.assertEqual(self.lib.floor_fixture(0,0,48),0)
        for yaw in range(64):
            self.assertEqual(camera.yaw,yaw)
            co,si=math.cos(yaw*math.tau/64),math.sin(yaw*math.tau/64)
            expected=[co*256,0,-si*256,0,0,256,0,-self.profile['camera']['eye_height'],si*256,0,co*256,0]
            self.assertLessEqual(max(abs(a-b) for a,b in zip(camera.view,expected)),0.5)
            self.step(p,camera,2)
        self.assertEqual(camera.yaw,0)

    def test_walking_turning_wall_stop_jump_and_reset(self):
        p,camera=self.start();self.step(p,camera,4)
        self.assertEqual((p.x,p.z),(0,self.profile['physics']['speed']))
        self.step(p,camera,2,16);self.assertEqual(camera.yaw,16)
        before=p.x;self.step(p,camera,4);self.assertEqual(p.x,before+self.profile['physics']['speed'])
        self.step(p,camera,16)
        self.assertGreater(p.y,0);self.assertFalse(p.grounded)
        self.step(p,camera,0,40);self.assertTrue(p.grounded)
        self.step(p,camera,4,100)
        self.assertLess(p.x,600*self.profile['scale']) # Original source walls stop forward movement.
        respawns=p.respawns;self.step(p,camera,15)
        self.assertEqual((p.x,p.y,p.z,camera.yaw,p.respawns),(0,0,0,0,respawns+1))
        self.step(p,camera,15);self.assertEqual(p.respawns,respawns+1)

    def test_region_boundary_respawn(self):
        p,camera=self.start();p.x=self.profile['selection_radius']*self.profile['scale']+64;self.step(p,camera)
        self.assertEqual((p.x,p.y,p.z,camera.yaw,p.respawns),(0,0,0,0,1))

    def test_reject_truncated_and_wrong_format(self):
        for data in (b'',b'PACK'+b'\0'*8,b'PACK'+struct.pack('<ii',12,64)):
            with self.assertRaises(ValueError):quake_assets.pak_entries(data)
        for data in (b'',struct.pack('<i',30)+b'\0'*120,struct.pack('<i',29)+struct.pack('<ii',124,20)+b'\0'*112):
            with self.assertRaises(ValueError):quake_assets.bsp_lumps(data)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'invalid-depth.json'
            for near in (32,256):
                profile=copy.deepcopy(self.profile);profile['camera']['near_z']=near
                path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    quake_assets.generate(path,ROOT/'build/quake-shareware/pak0.pak')

if __name__=='__main__':unittest.main()
