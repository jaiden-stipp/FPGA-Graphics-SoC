from test_support import ensure_castle_fixture
"""Independent arithmetic and source-preservation checks for rendering fixes."""
import ctypes as c,json,os,random,shutil,subprocess,unittest
from pathlib import Path
from soc import ROOT
from test_world_pipeline import STUB

class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'build/render-fixes/native';out.mkdir(parents=True,exist_ok=True)
        source=out/'render.c'
        source.write_text('#define WORLD_GPU_CAPABLE 0\n#include "render_interpolation.h"\n#include "'+(ROOT/'firmware/src/world.c').as_posix()+'"\n'+STUB+r'''
int32_t lerp_probe(int32_t a,int32_t b,uint32_t t){return game_render_lerp(a,b,t);}
uint32_t fraction_probe(uint32_t previous,uint32_t period,uint32_t now){game_runtime_clock_t c={previous,period,0};return game_render_fraction(&c,now);}
void intersection_probe(const int32_t*a,const int32_t*b,int32_t da,int32_t db,int32_t*out){
    clip_point_t x={a[0],a[1],a[2]},y={b[0],b[1],b[2]},q=intersection(x,y,da,db);
    out[0]=q.x;out[1]=q.y;out[2]=q.z;
}
''')
        dll=out/('render.dll' if os.name=='nt' else 'render.so')
        flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated']
        flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+n for n in ('lerp_probe','fraction_probe','intersection_probe')] if os.name=='nt' else ['-fPIC']
        subprocess.run([shutil.which('clang'),*flags,str(source),'firmware/src/player.c','firmware/src/game_services.c','firmware/ports/castle_rules.c','-o',str(dll)],cwd=ROOT,check=True)
        cls.lib=c.CDLL(str(dll));cls.lib.lerp_probe.argtypes=[c.c_int32,c.c_int32,c.c_uint32];cls.lib.lerp_probe.restype=c.c_int32
        cls.lib.fraction_probe.argtypes=[c.c_uint32]*3;cls.lib.fraction_probe.restype=c.c_uint32
        cls.lib.intersection_probe.argtypes=[c.POINTER(c.c_int32),c.POINTER(c.c_int32),c.c_int32,c.c_int32,c.POINTER(c.c_int32)]
    def test_lerp_matches_big_integer_floor(self):
        rng=random.Random(6600)
        for _ in range(3000):
            a,b=rng.randint(-100000,100000),rng.randint(-100000,100000);t=rng.randrange(65537)
            self.assertEqual(self.lib.lerp_probe(a,b,t),a+((b-a)*t//65536))
        for t,expected in ((0,-100),(32768,0),(65536,100),(70000,100)):
            self.assertEqual(self.lib.lerp_probe(-100,100,t),expected)
    def test_fraction_wrap_deadline_and_clamp(self):
        previous=0xfffffff0;period=1666667
        for elapsed in (0,1,period//2,period-1,period,period+500):
            self.assertEqual(self.lib.fraction_probe(previous,period,(previous+elapsed)&0xffffffff),min(65536,elapsed*65536//period))
    def test_reversed_shared_edges_are_identical_and_match_canonical_oracle(self):
        rng=random.Random(6601);P=c.c_int32*3
        for _ in range(3000):
            a=tuple(rng.randint(-50000,50000) for _ in range(3));b=tuple(rng.randint(-50000,50000) for _ in range(3))
            da,db=rng.randint(1,100000),-rng.randint(1,100000);x,y=P(),P()
            self.lib.intersection_probe(P(*a),P(*b),da,db,x);self.lib.intersection_probe(P(*b),P(*a),db,da,y)
            self.assertEqual(list(x),list(y))
            if a>b:a,b,da,db=b,a,db,da
            t=abs(da)*65536//(abs(da)+abs(db));self.assertEqual(list(x),[v+(w-v)*t//65536 for v,w in zip(a,b)])
    def test_shaded_world_retains_all_geometry_collision_and_actor_data(self):
        old=json.loads(ensure_castle_fixture(False).read_text());new=json.loads(ensure_castle_fixture(True).read_text())
        self.assertEqual(old['resident_scene']['meshes'],new['resident_scene']['meshes'])
        self.assertEqual(old['transitions'],new['transitions']);self.assertEqual(old['event_exits'],new['event_exits'])
        self.assertEqual(old['animation'],new['animation']);self.assertLessEqual(len(new['resident_scene']['palette']),256)
        for a,b in zip(old['areas'],new['areas']):
            self.assertEqual(a['vertices'],b['vertices']);self.assertEqual([t[:3] for t in a['triangles']],[t[:3] for t in b['triangles']]);self.assertEqual(a['collision'],b['collision'])
            self.assertEqual(a['triangle_room_masks'],b['triangle_room_masks'])
    def test_original_baked_shading_changes_actual_colors(self):
        old=json.loads(ensure_castle_fixture(False).read_text());new=json.loads(ensure_castle_fixture(True).read_text())
        op=old['resident_scene']['palette'];np=new['resident_scene']['palette']
        changes=sum(op[x[3]]!=np[y[3]] for a,b in zip(old['areas'],new['areas']) for x,y in zip(a['triangles'],b['triangles']))
        self.assertGreater(changes,0)

if __name__=='__main__':unittest.main()
