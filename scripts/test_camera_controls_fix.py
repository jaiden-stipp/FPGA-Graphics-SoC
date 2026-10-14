"""Independent rendered-axis, culling and mouse-edge regressions."""
import ctypes as c,json,subprocess,unittest
from pathlib import Path
import sm64_engine_slice as engine
from test_sm64_engine_slice import Result,load_reference
from test_sm64_visual_camera import configure
from test_support import native_flags

class CameraControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.diagnostic(True);cls.lib=configure(load_reference())
        dest=engine.ROOT/'build/camera-controls-fix';dest.mkdir(exist_ok=True)
        source=dest/'input-probe.c';source.write_text('''
#include "camera_input.h"
static engine_camera_input_t state;
uint32_t map_buttons(uint32_t buttons){return engine_input_buttons(buttons);}
void look_reset(void){state=(engine_camera_input_t){0};}
uint32_t map_look(uint32_t yaw,int32_t pitch){return engine_input_look(&state,yaw,pitch);}
''')
        dll=dest/'input-probe.dll'
        subprocess.run([str(engine.LLVM/'clang.exe'),*native_flags(['map_buttons','look_reset','map_look']),'-I'+str(engine.ROOT/'firmware/engine'),str(source),'-o',str(dll)],check=True)
        cls.input=c.CDLL(str(dll));cls.input.map_buttons.restype=cls.input.map_look.restype=c.c_uint32
    def test_mouse_sign_wrap_and_queued_edges(self):
        i=self.input;i.look_reset()
        self.assertEqual(i.map_look(128,0),0)
        self.assertEqual(i.map_look(160,16),256|1024) # Right/up mouse -> SDK C-left/up.
        self.assertEqual(i.map_look(96,-16),0) # Explicit release frame.
        self.assertEqual(i.map_look(96,-16),512|2048)
        i.look_reset();self.assertEqual(i.map_look(240,0),0)
        self.assertEqual(i.map_look(16,0),256) # +32 crossing the 8-bit wrap.
        i.look_reset();i.map_look(0,0)
        self.assertEqual([i.map_look(96,0) for _ in range(5)],[256,0,256,0,256])
    def test_wasd_moves_in_rendered_axes_at_four_headings(self):
        lib=self.lib;view=(c.c_int16*12)();rows=[]
        for heading in (0,16384,32768,49152):
            for buttons,axis,sign in ((1,0,-1),(2,0,1),(4,2,1),(8,2,-1)):
                lib.sm64_engine_init_heading((c.c_int32*3)(-1328,260,4664),heading)
                lib.sm64_engine_camera_step(view,4)
                origin=[lib.sm64_engine_probe(k) for k in (2,3,4)]
                import struct
                floats=lambda words:[struct.unpack('<f',struct.pack('<I',v))[0] for v in words]
                start=floats(origin);rotation=list(view)
                # Heading is fixed to the initial real camera for this movement
                # fixture; camera auto-pan does not redefine the tested axes.
                yaw=lib.sm64_engine_visual_probe(3)>>8
                for tick in range(24):
                    r=Result();lib.sm64_engine_update(self.input.map_buttons(buttons),yaw,c.byref(r))
                    self.assertEqual(r.fault,0)
                end=floats([lib.sm64_engine_probe(k) for k in (2,3,4)])
                dot=sum((end[k]-start[k])*rotation[axis*4+k] for k in (0,2))/256
                self.assertGreater(dot*sign,0,(heading,buttons,dot))
                rows.append({'heading':heading,'buttons':buttons,'render_axis_displacement':dot})
        (engine.ROOT/'build/camera-controls-fix/input-directions.json').write_text(json.dumps(rows,indent=2)+'\n')
    def test_real_ground_front_faces_follow_gpu_culling_convention(self):
        lib=self.lib;view=(c.c_int16*12)();lib.sm64_engine_init_heading((c.c_int32*3)(-1328,260,4664),32768)
        for tick in range(60):
            r=Result();lib.sm64_engine_update(0,256,c.byref(r));lib.sm64_engine_camera_step(view,4)
        world=json.loads((engine.OUT/'assets/world.json').read_text());area=world['areas'][0]
        import struct
        eye=[struct.unpack('<f',struct.pack('<I',lib.sm64_engine_visual_probe(k)))[0] for k in (4,5,6)]
        fronts=0
        for indices in area['triangles']:
            points=[area['vertices'][j] for j in indices[:3]]
            a,b,d=points
            # Independent source-space floor normal, not an adapter self-check.
            ny=(b[2]-a[2])*(d[0]-a[0])-(b[0]-a[0])*(d[2]-a[2])
            if ny<=0:continue
            normal=[(b[1]-a[1])*(d[2]-a[2])-(b[2]-a[2])*(d[1]-a[1]),ny,(b[0]-a[0])*(d[1]-a[1])-(b[1]-a[1])*(d[0]-a[0])]
            if sum(normal[k]*(eye[k]-a[k]) for k in range(3))<=0:continue
            projected=[]
            for point in points:
                local=[(point[k]-(-1328,260,4664)[k])*4 for k in range(3)]
                q=[sum(local[k]*view[row*4+k] for k in range(3))/256+view[row*4+3] for row in range(3)]
                if q[2]<257:break
                projected.append((160+256*q[0]/q[2],120-256*q[1]/q[2]))
            if len(projected)!=3:continue
            a,b,d=projected
            fan=(d[0]-a[0])*(b[1]-a[1])-(d[1]-a[1])*(b[0]-a[0])
            if abs(fan)<.01:continue
            self.assertLess(fan,0,'A source floor facing the eye must survive GPU backface culling')
            fronts+=1
        self.assertGreater(fronts,0)

if __name__=='__main__':unittest.main()
