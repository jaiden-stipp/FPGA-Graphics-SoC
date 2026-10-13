"""Original engine replay and explicit software-math ABI regression checks."""
import ctypes as c,json,math,random,struct,unittest
from pathlib import Path
import sm64_engine_slice as engine

class Result(c.Structure):
    _fields_=[(name,c.c_int32 if i<4 else c.c_uint32) for i,name in enumerate(('x','y','z','velocity_y','grounded','facing','action','fault'))]

def input_at(tick):return 0 if tick<8 else 4 if tick<20 else 20 if tick<27 else 4 if tick<42 else 0
def load_reference():
    lib=c.CDLL(str(engine.OUT/'engine.dll'))
    lib.sm64_engine_init.argtypes=[c.POINTER(c.c_int32)]
    lib.sm64_engine_update.argtypes=[c.c_uint32,c.c_uint32,c.POINTER(Result)]
    lib.sm64_engine_probe.restype=c.c_uint32
    return lib
def replay(lib):
    lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664));rows=[]
    for tick in range(96):
        r=Result();lib.sm64_engine_update(input_at(tick),0,c.byref(r))
        rows.append({'tick':tick,'buttons':input_at(tick),'position':[r.x,r.y,r.z],'bits':[lib.sm64_engine_probe(i) for i in (2,3,4)],'action':r.action,'fault':r.fault,'grounded':r.grounded})
    return rows
def f32(x):
    try:return struct.unpack('<f',struct.pack('<f',x))[0]
    except OverflowError:return math.copysign(math.inf,x)
def bits(x):return struct.unpack('<I',struct.pack('<f',x))[0]

class EngineSlice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):engine.diagnostic(True);cls.lib=load_reference()
    def test_walk_jump_land_and_repeatable_reset(self):
        first=replay(self.lib);second=replay(self.lib)
        self.assertEqual(first,second);self.assertTrue(all(r['fault']==0 for r in first))
        self.assertLess(first[-1]['position'][2],first[0]['position'][2])
        self.assertGreater(max(r['position'][1] for r in first),first[0]['position'][1])
        self.assertTrue(any(not r['grounded'] for r in first));self.assertEqual(first[-1]['grounded'],1)
        self.assertEqual(first[-1]['action'],first[0]['action'])
        (engine.OUT/'native-trace.json').write_text(json.dumps(first,indent=2)+'\n')
    def test_original_surface_grid_capacity(self):
        replay(self.lib);report=json.loads((engine.OUT/'source-report.json').read_text())
        self.assertEqual(self.lib.sm64_engine_probe(5),report['terrain_faces'])
        self.assertEqual(self.lib.sm64_engine_probe(6),report['derived_surface_nodes'])
    def test_repeated_jump_routes_include_rollout_steep_and_wall_transitions(self):
        seen=set()
        for yaw in (0,32,64,96,128,160,192,224):
            for buttons in (4,5,6,8,1,2):
                self.lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664))
                for tick in range(900):
                    result=Result()
                    self.lib.sm64_engine_update(buttons|(16 if tick%45<7 else 0),yaw,c.byref(result))
                    seen.add(result.action)
                    self.assertEqual(result.fault,0,(yaw,buttons,tick,hex(result.action)))
                for tick in range(60):
                    result=Result();self.lib.sm64_engine_update(0,yaw,c.byref(result))
                    seen.add(result.action)
                    self.assertEqual(result.fault,0,('released',yaw,buttons,tick,hex(result.action)))
        self.assertIn(0x03000885,seen) # Original steep jump.
        self.assertIn(0x010008ad,seen) # Original backward rollout.
        self.assertIn(0x000008a7,seen) # Original airborne wall hit.
        self.assertIn(0x0c400209,seen) # Original wall-standing after release.
    def test_all_original_animation_ids_are_present(self):
        text=(engine.OUT/'animations.inc').read_text();report=json.loads((engine.OUT/'source-report.json').read_text())
        self.assertIn('anim_C3',text);self.assertIn('anim_70',text);self.assertEqual(report['animation_tables'],209)
    def test_softfloat_matches_independent_f32_reference(self):
        rng=random.Random(0x534d3634)
        pairs=[(0.0,-0.0),(1.0,3.0),(-42.5,0.25),(2**-126,2**-126)]
        for _ in range(1200):
            a=struct.unpack('<f',struct.pack('<I',rng.getrandbits(32)))[0];b=struct.unpack('<f',struct.pack('<I',rng.getrandbits(32)))[0]
            if math.isfinite(a) and math.isfinite(b):pairs.append((a,b))
        for name,op in [('__addsf3',lambda a,b:a+b),('__subsf3',lambda a,b:a-b),('__mulsf3',lambda a,b:a*b),('__divsf3',lambda a,b:a/b)]:
            fn=getattr(self.lib,name);fn.argtypes=[c.c_float,c.c_float];fn.restype=c.c_float
            for a,b in pairs:
                if name=='__divsf3' and b==0:continue
                self.assertEqual(bits(fn(a,b)),bits(f32(op(a,b))),(name,a,b))
        sqrt=self.lib.sqrtf;sqrt.argtypes=[c.c_float];sqrt.restype=c.c_float
        for a,_ in pairs:
            if a>=0:self.assertEqual(bits(sqrt(a)),bits(f32(math.sqrt(a))))
    def test_integer_helpers_across_word_boundaries(self):
        rng=random.Random(0x52563332);mul=getattr(self.lib,'__muldi3');mul.argtypes=[c.c_uint64,c.c_uint64];mul.restype=c.c_uint64
        shifts=[]
        for name,signed in [('__ashldi3',False),('__lshrdi3',False),('__ashrdi3',True)]:
            fn=getattr(self.lib,name);fn.argtypes=[c.c_int64 if signed else c.c_uint64,c.c_int];fn.restype=c.c_int64 if signed else c.c_uint64;shifts.append(fn)
        for _ in range(500):
            a=rng.getrandbits(64);b=rng.getrandbits(64);self.assertEqual(mul(a,b),(a*b)&((1<<64)-1))
            for n in (0,1,16,31,32,33,63):
                self.assertEqual(shifts[0](a,n),(a<<n)&((1<<64)-1));self.assertEqual(shifts[1](a,n),a>>n)
                signed=c.c_int64(a).value;self.assertEqual(shifts[2](signed,n),signed>>n)
    def test_unsigned_division(self):
        fn=getattr(self.lib,'__udivsi3');fn.argtypes=[c.c_uint32,c.c_uint32];fn.restype=c.c_uint32
        for a,b in [(0,1),(0xffffffff,1),(0xffffffff,0xffffffff),(0x80000000,3),(0xffffffff,0x80000000),(123,0)]:self.assertEqual(fn(a,b),a//b if b else 0xffffffff)
    def test_source_closure_retains_original_jump_callback(self):
        closure=json.loads((engine.OUT/'native-source-closure.json').read_text())
        self.assertIn('set_triple_jump_action',closure)
        for name in ('act_idle','act_walking','act_jump','perform_air_step','perform_ground_step','find_floor','find_wall_collisions','read_surface_data'):self.assertIn(name,closure)

if __name__=='__main__':unittest.main()
