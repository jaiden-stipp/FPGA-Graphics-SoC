"""Check production admission bounds and exact expanded GPU triangle streams."""
import ctypes as c
import os
from pathlib import Path
import random
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stddef.h>
#include "world.h"
#include "gfx.h"
#include "gfx_protocol.h"
void *memcpy(void *d,const void *s,size_t n){unsigned char *a=d;const unsigned char *b=s;for(size_t i=0;i<n;++i)a[i]=b[i];return d;}
#include "WORLD_SOURCE"
static scene_vertex_t store[16][128];
static scene_triangle_t faces[16][256];
static uint32_t face_count[16],hash,draw_count,mesh_count;
static int16_t read16(const uint8_t *p){return (int16_t)(((uint16_t)p[0]<<8)|p[1]);}
static void emit(const int32_t *q,uint32_t color){for(uint32_t j=0;j<9;++j)hash=(hash^(uint32_t)q[j])*16777619u;hash=(hash^color)*16777619u;++draw_count;}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t){(void)v;face_count[h]=t;return 0;}
int game_mesh_frame(uint8_t h,const scene_vertex_t *v,uint32_t n){for(uint32_t i=0;i<n;++i)store[h][i]=v[i];return 0;}
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n){
    (void)n;
    if(op==GFX_OP_UPLOAD_INDICES){uint32_t start=(uint16_t)read16(p+1);for(uint32_t i=0;i<p[3];++i){uint32_t b=4+4*i;faces[p[0]][start+i]=(scene_triangle_t){p[b],p[b+1],p[b+2],p[b+3]};}return 0;}
    if(op==GFX_OP_DRAW_TRIANGLE){int32_t q[9];for(uint32_t j=0;j<9;++j)q[j]=read16(p+2*j);emit(q,p[18]);return 0;}
    return -1;
}
int gfx_draw_matrix(uint8_t h,const int16_t m[12]){
    ++mesh_count;
    for(uint32_t i=0;i<face_count[h];++i){scene_triangle_t t=faces[h][i];uint8_t ix[3]={t.a,t.b,t.c};int32_t q[9];
        for(uint32_t j=0;j<3;++j){scene_vertex_t p=store[h][ix[j]];for(uint32_t row=0;row<3;++row){uint32_t b=4*row;q[3*j+row]=((p.x*m[b]+p.y*m[b+1]+p.z*m[b+2])>>8)+m[b+3];}}
        emit(q,t.color);
    }return 0;
}
int admission_probe(const int16_t *origin,const int16_t *bounds,const int32_t *position,const int16_t *view,int16_t *out){
    world_chunk_t ch={0};ch.mesh.vertex_count=3;ch.mesh.triangle_count=1;
    for(uint32_t i=0;i<3;++i)ch.origin[i]=origin[i];for(uint32_t i=0;i<6;++i)ch.bounds[i]=bounds[i];
    player_t p={0};p.x=position[0];p.y=position[1];p.z=position[2];return safe_matrix(&ch,&p,view,out);
}
void transform_probe(const int32_t *point,const int32_t *position,const int16_t *view,int32_t *out){player_t p={0};p.x=position[0];p.y=position[1];p.z=position[2];clip_point_t q=transform(point[0],point[1],point[2],&p,view);out[0]=q.x;out[1]=q.y;out[2]=q.z;}
uint32_t stream_fixture(uint32_t reserved,uint32_t stale){
    static const scene_vertex_t vertices[]={{-20,0,400},{0,20,400},{20,0,400}};
    static const scene_triangle_t ts[]={{0,1,2,9}};
    static const world_chunk_t chunks[]={
      {{vertices,ts,3,1},{0,0,0},{-20,20,0,20,400,400},0},
      {{vertices,ts,3,1},{0,0,0},{-20,20,0,20,400,400},0},
      {{vertices,ts,3,1},{0,0,0},{-20,20,0,20,400,400},0}};
    static const player_world_t w={0,0,0,0,0,0,0,8,18,128,12,3,30,-1500};
    static const world_area_t a={chunks,3,&w,0,0,0,0,0,0,0,0,0,0,0,0,0};
    world_chunk_t mutable_chunks[3];for(uint32_t i=0;i<3;++i)mutable_chunks[i]=chunks[i];
    world_area_t current=a;current.chunks=mutable_chunks;
    if(stale==2){mutable_chunks[0].bounds[0]=-10;mutable_chunks[0].bounds[1]=10;}
    player_t p={0};int16_t v[12]={256,0,0,0,0,256,0,0,0,0,256,0};world_select(&current,&p);
    if(world_prepare(&current,&p,v,reserved))return 0;
    if(stale==1)p.x+=1;
    if(stale==3)v[3]+=1;
    hash=2166136261u;draw_count=mesh_count=0;
    if(world_draw(&current,&p,v,reserved))return 0;
    if(draw_count!=3)return 0;
    return hash;
}
uint32_t fixture_mesh_count(void){return mesh_count;}
'''

class TerrainOffloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'build/terrain-offload-tests';out.mkdir(parents=True,exist_ok=True)
        source=out/'probe.c';source.write_text(HARNESS.replace('WORLD_SOURCE',(ROOT/'firmware/src/world.c').as_posix()))
        names=['admission_probe','transform_probe','stream_fixture','fixture_mesh_count']
        cls.libs=[]
        for direct in (False,True):
            dll=out/('direct' if direct else 'safe');dll=dll.with_suffix('.dll' if os.name=='nt' else '.so')
            flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated']
            flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry',*['-Wl,/export:'+n for n in names]] if os.name=='nt' else ['-fPIC']
            if direct:flags+=['-DWORLD_FORCE_DIRECT=1']
            subprocess.run([shutil.which('clang'),*flags,str(source),'firmware/src/player.c','-o',str(dll)],cwd=ROOT,check=True)
            lib=c.CDLL(str(dll));lib.stream_fixture.restype=c.c_uint32
            cls.libs.append(lib)

    def admit(self,origin,bounds,position,view):
        out=(c.c_int16*12)()
        result=self.libs[0].admission_probe((c.c_int16*3)(*origin),(c.c_int16*6)(*bounds),(c.c_int32*3)(*position),(c.c_int16*12)(*view),out)
        return result,list(out)

    def test_exact_expanded_triangle_stream_and_capacity_fallback(self):
        for reserved in (2,15,16-1):
            safe=self.libs[0].stream_fixture(reserved,0)
            self.assertNotEqual(safe,0)
            self.assertEqual(safe,self.libs[1].stream_fixture(reserved,0))
            self.assertEqual(self.libs[0].fixture_mesh_count(),min(3,16-reserved))

    def test_changed_pose_between_prepare_and_draw_falls_back(self):
        for mode in (1,3):
            self.assertEqual(self.libs[0].stream_fixture(2,mode),self.libs[1].stream_fixture(2,mode))
            self.assertEqual(self.libs[0].fixture_mesh_count(),0)

    def test_incorrect_metadata_box_falls_back_without_losing_faces(self):
        self.assertEqual(self.libs[0].stream_fixture(2,2),self.libs[1].stream_fixture(2,2))
        self.assertEqual(self.libs[0].fixture_mesh_count(),2)

    def test_rounding_near_far_and_side_plane_guards(self):
        identity=[256,0,0,0,0,256,0,0,0,0,256,0]
        self.assertEqual(self.admit([0,0,0],[-20,20,0,20,400,400],[0,0,0],identity)[0],1)
        for bounds in ([-20,20,0,20,50,100],[-20,20,0,20,7000,8000],[-1000,1000,0,20,400,400]):
            self.assertEqual(self.admit([0,0,0],bounds,[0,0,0],identity)[0],0)
        fractional=identity[:];fractional[1]=1
        self.assertEqual(self.admit([0,1,0],[-20,20,0,20,400,400],[0,0,0],fractional)[0],0)
        self.assertEqual(self.admit([0,0,0],[-20,20,0,20,400,400],[100000,0,0],identity)[0],0)

    def test_random_admitted_bounds_prove_all_sampled_vertices_equal(self):
        rng=random.Random(417);admitted=0
        for trial in range(1000):
            # Integral-origin cases exercise signed flooring and conservative
            # bounds, with shear/rotation-like coefficients and translations.
            origin=[rng.randrange(-100,101),rng.randrange(-100,101),rng.randrange(300,901)]
            bounds=[x+d for x in origin for d in (-20,20)]
            position=[rng.randrange(-50,51),rng.randrange(-50,51),0]
            view=[256,rng.choice([-64,0,64]),0,rng.randrange(-5,6),0,256,rng.choice([-64,0,64]),rng.randrange(-5,6),0,0,256,0]
            yes,m=self.admit(origin,bounds,position,view)
            if not yes:continue
            admitted+=1
            for sample in range(12):
                point=[rng.randrange(bounds[2*i],bounds[2*i+1]+1) for i in range(3)]
                cpu=(c.c_int32*3)();self.libs[0].transform_probe((c.c_int32*3)(*point),(c.c_int32*3)(*position),(c.c_int16*12)(*view),cpu)
                local=[point[i]-origin[i] for i in range(3)]
                gpu=[sum(local[j]*m[4*i+j] for j in range(3))//256+m[4*i+3] for i in range(3)]
                self.assertEqual(list(cpu),gpu)
                x,y,z=gpu;self.assertTrue(257<=z<=30000 and abs(x)<=32764 and abs(y)<=32764)
                self.assertTrue(x*256+z*160>=0 and -x*256+z*160>=0 and y*256+z*120>=0 and -y*256+z*120>=0)
        self.assertGreater(admitted,100)

if __name__=='__main__':unittest.main()
