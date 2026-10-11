"""Production CPU clipping compared with independent projected coverage."""
import ctypes as c
import json
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
static int32_t output[64*9];static uint32_t count;
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n){(void)n;if(op==GFX_OP_DRAW_TRIANGLE){for(uint32_t j=0;j<9;++j)output[count*9+j]=(int16_t)(((uint16_t)p[2*j]<<8)|p[2*j+1]);++count;}return 0;}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t){(void)h;(void)v;(void)t;return 0;}
int gfx_draw_matrix(uint8_t h,const int16_t *m){(void)h;(void)m;return 0;}
int game_mesh_frame(uint8_t h,const scene_vertex_t *v,uint32_t n){(void)h;(void)v;(void)n;return 0;}
int32_t interpolation_probe(int32_t a,int32_t b,int32_t t){return interpolate(a,b,t);}
int clip_probe(const int32_t *xyz,int32_t *result){count=0;for(uint32_t j=0;j<3;++j){direct_points[j]=(clip_point_t){xyz[3*j],xyz[3*j+1],xyz[3*j+2]};direct_outcodes[j]=0;for(uint32_t k=0;k<6;++k)if(plane(direct_points[j],k)<0)direct_outcodes[j]|=1u<<k;}
scene_triangle_t t={0,1,2,1};if(direct(&t))return -1;for(uint32_t i=0;i<count*9;++i)result[i]=output[i];return (int)count;}
'''

def build_probe(world_source=None):
    out=ROOT/'build/screen-edge-tests';out.mkdir(parents=True,exist_ok=True)
    world_source=world_source or ROOT/'firmware/src/world.c'
    suffix='baseline' if world_source!=ROOT/'firmware/src/world.c' else 'candidate'
    source=out/(suffix+'.c')
    harness=HARNESS
    if suffix=='baseline':harness=harness.replace('int32_t interpolation_probe(int32_t a,int32_t b,int32_t t){return interpolate(a,b,t);}','')
    source.write_text(harness.replace('WORLD_SOURCE',world_source.as_posix()))
    dll=out/(suffix+('.dll' if os.name=='nt' else '.so'))
    flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated']
    flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:clip_probe'] if os.name=='nt' else ['-fPIC']
    if suffix=='candidate' and os.name=='nt':flags+=['-Wl,/export:interpolation_probe']
    subprocess.run([shutil.which('clang'),*flags,str(source),'firmware/src/player.c','-o',str(dll)],cwd=ROOT,check=True)
    lib=c.CDLL(str(dll));lib.clip_probe.argtypes=[c.POINTER(c.c_int32),c.POINTER(c.c_int32)];return lib

def emitted(lib,points):
    result=(c.c_int32*(64*9))();n=lib.clip_probe((c.c_int32*9)(*(v for p in points for v in p)),result)
    if n<0:raise AssertionError('CPU rejected representable clipped triangle')
    return [[tuple(result[9*i+3*j+k] for k in range(3)) for j in range(3)] for i in range(n)]

def reference(points):
    poly=[tuple(float(v) for v in p) for p in points]
    planes=[lambda p:p[2]-257,lambda p:30000-p[2],lambda p:p[0]*256+p[2]*160,
            lambda p:-p[0]*256+p[2]*160,lambda p:p[1]*256+p[2]*120,lambda p:-p[1]*256+p[2]*120]
    for plane in planes:
        out=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            da,db=plane(a),plane(b)
            if da>=0:out.append(a)
            if (da<0)!=(db<0):
                t=da/(da-db);out.append(tuple(a[k]+t*(b[k]-a[k]) for k in range(3)))
        poly=out
    return [[poly[0],poly[i],poly[i+1]] for i in range(1,len(poly)-1)]

def project(p):return (160+256*p[0]/p[2],120-256*p[1]/p[2])
def covers(tris,x,y):
    for tri in tris:
        p=[project(v) for v in tri]
        edges=[(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]) for a,b in zip(p,p[1:]+p[:1])]
        if min(edges)>=-1e-7 or max(edges)<=1e-7:return True
    return False

class ScreenEdgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=build_probe()

    def test_exact_interpolation_without_high_product_instruction(self):
        self.lib.interpolation_probe.argtypes=[c.c_int32,c.c_int32,c.c_int32]
        self.lib.interpolation_probe.restype=c.c_int32
        rng=random.Random(841)
        pairs=[(-100000,100000),(100000,-100000),(0,2147483647),(-2147483648,-1)]
        pairs += [(rng.randrange(-1000000,1000001),rng.randrange(-1000000,1000001)) for _ in range(200)]
        for a,b in pairs:
            for t in (0,1,32767,32768,65535,65536):
                self.assertEqual(self.lib.interpolation_probe(a,b,t),a+((b-a)*t//65536))

    def test_preserved_large_left_edge_reproduction(self):
        points=[(-14856,12446,-19861),(-32402,-31455,26451),(54380,20460,-3533)]
        actual=emitted(self.lib,points)
        for y in range(8,153,16):self.assertTrue(covers(actual,3,y),(3,y))

    def test_crossing_triangles_keep_interior_edge_coverage(self):
        rng=random.Random(501);failures=[]
        # Sample safely inside the viewport; large gaps are not a one-pixel
        # raster fill convention or an intentional far-plane exclusion.
        probes=[(x,y) for x in (3,8,16,303,311,316) for y in range(8,233,16)]
        probes += [(x,y) for y in (3,8,16,223,231,236) for x in range(8,313,16)]
        for i in range(300):
            points=[(rng.randrange(-60000,60001),rng.randrange(-40000,40001),rng.randrange(-20000,30001)) for j in range(3)]
            expected=reference(points);actual=emitted(self.lib,points)
            missing=[p for p in probes if covers(expected,*p) and all(covers(expected,p[0]+dx,p[1]+dy) for dx,dy in ((-2,0),(2,0),(0,-2),(0,2))) and not covers(actual,*p)]
            if missing:failures.append({'triangle':points,'missing':missing,'emitted':actual})
        out=ROOT/'build/screen-edge-tests/results.json';out.write_text(json.dumps({'seed':501,'triangles':300,'failures':failures},indent=2))
        self.assertEqual(len(failures),0,f'{len(failures)} triangles lose interior edge coverage; see {out}')

if __name__=='__main__':unittest.main()
