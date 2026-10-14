"""Original animation/channel and normal Lakitu regression evidence."""
import ctypes as c,json,math,struct,unittest
import animation_assets as assets
import sm64_engine_slice as engine
from test_sm64_engine_slice import Result,load_reference

def hash16(values):
    h=2166136261
    for v in values:
        for b in struct.pack('<H',v&65535):h=((h^b)*16777619)&0xffffffff
    return h

def configure(lib):
    lib.sm64_engine_pose.argtypes=[c.POINTER(c.c_int16),c.c_uint32,c.c_uint32]
    lib.sm64_engine_camera_step.argtypes=[c.POINTER(c.c_int16),c.c_uint32]
    lib.sm64_engine_test_float_pose.argtypes=lib.sm64_engine_pose.argtypes
    lib.sm64_engine_visual_probe.restype=c.c_uint32
    lib.sm64_engine_test_animation.restype=c.c_uint32
    lib.sm64_engine_init_heading.argtypes=[c.POINTER(c.c_int32),c.c_uint32]
    return lib

def visual_replay(lib):
    lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664));rows=[]
    for tick in range(96):
        buttons=0 if tick<8 else 4 if tick<20 else 20 if tick<27 else 4 if tick<42 else 0
        buttons|=512 if tick==48 else 2048 if tick==72 else 0
        result=Result();lib.sm64_engine_update(buttons,256,c.byref(result))
        view=(c.c_int16*12)();pose=(c.c_int16*(136*3))()
        lib.sm64_engine_camera_step(view,4)
        if lib.sm64_engine_pose(pose,136,4):raise ValueError('Pose rejected')
        rows.append([lib.sm64_engine_probe(0),result.action]+[lib.sm64_engine_probe(k) for k in (2,3,4)]+[lib.sm64_engine_visual_probe(k) for k in range(10)]+[hash16(pose),hash16(view)]+[v&0xffffffff for v in view])
    return rows

class VisualCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.diagnostic(True);cls.lib=configure(load_reference())
        cls.world=json.loads((engine.OUT/'assets/world.json').read_text())
    def test_original_all_animation_ids_and_last_frames_fit_mesh(self):
        lib=self.lib;lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664));pose=(c.c_int16*408)()
        reference=(c.c_int16*408)();maximum=0
        for animation in range(209):
            end=lib.sm64_engine_test_animation(animation,0)
            for frame in (0,end-1):
                lib.sm64_engine_test_animation(animation,frame)
                self.assertEqual(lib.sm64_engine_pose(pose,136,4),0,(animation,frame))
                self.assertEqual(lib.sm64_engine_test_float_pose(reference,136,4),0)
                error=max(abs(a-b) for a,b in zip(pose,reference));maximum=max(maximum,error)
                self.assertLessEqual(error,1,(animation,frame,error))
                self.assertEqual(lib.sm64_engine_visual_probe(0),animation)
                self.assertEqual(lib.sm64_engine_visual_probe(1),frame)
                self.assertTrue(any(pose))
        self.assertEqual(lib.sm64_engine_probe(0),0)
        self.assertEqual(lib.sm64_engine_pose(pose,135,4),-1)
        self.assertEqual(lib.sm64_engine_pose(pose,136,0),-1)
        (engine.OUT/'visual-quantization.json').write_text(json.dumps({'animation_ids':209,'frames_per_id':2,'vertices_per_pose':136,'maximum_coordinate_error_gpu_units':maximum,'source_units_per_gpu_unit':.25,'scope':'Native animation first/last frame matrix-to-vertex comparison; fixed mesh switches, normal unsquished model'},indent=2)+'\n')
    def test_idle_vertices_match_independent_original_channel_reference(self):
        lib=self.lib;lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664));pose=(c.c_int16*408)()
        rig=self.world['animation'];clip=assets.clip(engine.ROOT/'external/sm64',{'role':'idle','source':'assets/anims/anim_C5.inc.c','symbol':'anim_C5'},20)
        for frame in (0,12,clip['end']-1):
            lib.sm64_engine_test_animation(0xc5,frame);self.assertEqual(lib.sm64_engine_pose(pose,136,4),0)
            matrices=assets.pose(rig['joints'],clip,frame)
            for i,v in enumerate(rig['vertex_sources']):
                expected=list(assets.vertex(matrices[v['joint']],v['local']))
                # The old shared clip reference intentionally drops lateral
                # root motion; the engine visual bridge must retain it.
                for k in (0,2):expected[k]+=clip['channels'][k][min(frame-clip['start'],len(clip['channels'][k])-1)]
                for k in range(3):self.assertLessEqual(abs(pose[i*3+k]-expected[k]),1.1,(frame,i,k))
    def test_lakitu_replay_reset_and_view_projection(self):
        first=visual_replay(self.lib);second=visual_replay(self.lib)
        self.assertEqual(first,second);self.assertTrue(all(r[0]==0 for r in first))
        self.assertGreater(len({r[15] for r in first}),20) # Animation pose hashes.
        self.assertGreater(len({r[16] for r in first}),20) # Camera matrix hashes.
        for row in first:
            view=[v if v<0x80000000 else v-0x100000000 for v in row[17:]]
            for axis in range(3):self.assertAlmostEqual(sum(v*v for v in view[axis*4:axis*4+3])/65536,1,delta=.02)
            self.assertGreater(view[11],0) # Mario is in front of the camera.
        (engine.OUT/'visual-native-trace.json').write_text(json.dumps(first,indent=2)+'\n')
    def test_camera_movement_water_and_cbuttons_do_not_fault(self):
        lib=self.lib;view=(c.c_int16*12)();pose=(c.c_int16*408)();modes=set()
        for keys in (4,8,5,6):
            lib.sm64_engine_init((c.c_int32*3)(-1328,260,4664))
            for tick in range(900):
                result=Result();buttons=keys|(16 if tick%45<7 else 0)|(512 if tick%200==100 else 0)
                lib.sm64_engine_update(buttons,256,c.byref(result));lib.sm64_engine_camera_step(view,4)
                self.assertEqual(lib.sm64_engine_pose(pose,136,4),0)
                self.assertEqual(lib.sm64_engine_probe(0),0,(keys,tick))
                modes.add(lib.sm64_engine_visual_probe(2))
        self.assertIn(16,modes) # CAMERA_MODE_FREE_ROAM.
    def test_c_up_exit_and_original_script_spawn_heading(self):
        lib=self.lib;view=(c.c_int16*12)();pose=(c.c_int16*408)()
        lib.sm64_engine_init_heading((c.c_int32*3)(-1328,260,4664),32768)
        self.assertEqual(lib.sm64_engine_probe(15),32768)
        for tick in range(60):
            result=Result();lib.sm64_engine_update(1024 if tick in (5,10) else 64 if tick==40 else 0,256,c.byref(result))
            lib.sm64_engine_camera_step(view,4)
            self.assertEqual(lib.sm64_engine_pose(pose,136,4),0)
            self.assertEqual(lib.sm64_engine_probe(0),0)
            if tick==30:self.assertEqual(lib.sm64_engine_visual_probe(2),6)
        self.assertNotEqual(lib.sm64_engine_visual_probe(2),6)

if __name__=='__main__':unittest.main()
