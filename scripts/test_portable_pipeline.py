from test_support import linked_test_packages
"""Test shared compilation, explicit capability failures and independent ports."""
import copy
import ctypes as c
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import portable_game
import load_game
import quake_assets
import target_capabilities
from test_player import Player

ROOT=Path(__file__).resolve().parents[1]
class PortableTests(unittest.TestCase):
    def setUp(self):self.room=json.loads((ROOT/'examples/portable-room/scene.json').read_text())
    def test_quake_roundtrip_preserves_selected_geometry(self):
        profile=json.loads((ROOT/'profiles/quake-e1m1.json').read_text())
        expected=quake_assets.prepare(ROOT/'build/quake-shareware/pak0.pak',profile)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'scene.json'
            portable_game.export_quake(ROOT/'build/quake-shareware/pak0.pak',ROOT/'profiles/quake-e1m1.json',path)
            actual=portable_game.compile_scene(json.loads(path.read_text()))
        self.assertEqual(actual[:4],expected[:4])
        self.assertEqual(actual[4]['source_triangles'],786)
        self.assertLessEqual(actual[4]['maximum_quantization_error_gpu_units'],0.5)

    def test_shared_chunks_retain_every_triangle(self):
        scene=copy.deepcopy(self.room);floor=scene['meshes'][0]
        floor['triangles']=floor['triangles']*129;scene['meshes']=[floor]
        chunks,_,_,_,report=portable_game.compile_scene(scene)
        self.assertEqual(sum(len(t) for _,t in chunks),258)
        self.assertEqual([len(t) for _,t in chunks],[256,2])
        self.assertEqual(sum(len(c['triangles']) for c in report['chunk_source_triangles']),258)

    def test_explicit_axis_reflection_keeps_floor_normal(self):
        scene=copy.deepcopy(self.room);scene['coordinates']['axes']=[-1,2,3]
        chunks,_,floors,_,report=portable_game.compile_scene(scene)
        self.assertTrue(report['winding_reflected']);self.assertTrue(floors)
        vertices,triangles=chunks[0]
        self.assertGreater(portable_game.area([vertices[i] for i in triangles[0][:3]])[1],0)

    def test_unsupported_features_are_not_flattened(self):
        for feature in ('textures','alpha-blending','os','cpu-floating-point','runtime-scene-streaming'):
            scene=copy.deepcopy(self.room);scene['target']['required_features'].append(feature)
            with self.assertRaisesRegex(ValueError,'cannot provide'):portable_game.compile_scene(scene)

    def test_capacity_failure_does_not_select_or_drop_faces(self):
        scene=copy.deepcopy(self.room);base=scene['meshes'][0]
        scene['meshes']=[dict(copy.deepcopy(base),id='floor-'+str(i)) for i in range(17)]
        with self.assertRaisesRegex(ValueError,'17 resident mesh handles'):portable_game.compile_scene(scene)

    def test_bad_geometry_and_numeric_conversion_fail(self):
        for mutation in ('nan','range','collapsed','palette','axes','near'):
            scene=copy.deepcopy(self.room)
            if mutation=='nan':scene['meshes'][0]['vertices'][0][0]=float('nan')
            if mutation=='range':scene['coordinates']['scale']=100000
            if mutation=='collapsed':scene['coordinates']['scale']=.00001
            if mutation=='palette':scene['meshes'][0]['triangles'][0][3]=256
            if mutation=='axes':scene['coordinates']['axes']=[1,1,2]
            if mutation=='near':scene['controller']['camera']['near_z']=32
            with self.assertRaises(ValueError):portable_game.compile_scene(scene)

    def test_custom_port_does_not_require_shared_physics(self):
        scene=json.loads((ROOT/'examples/custom-port/scene.json').read_text())
        chunks,palette,floors,walls,report=portable_game.compile_scene(scene,explorer=False)
        self.assertEqual((report['world_meshes'],report['actor_meshes']),(1,1))
        self.assertFalse(report['controller_present']);self.assertEqual(report['physics'],{})
        header=portable_game.header(chunks,palette,floors,walls,report)
        self.assertNotIn('player_world_t portable_world',header)
        with self.assertRaises(ValueError):portable_game.compile_scene(scene)

    def test_package_target_gate_precedes_cpu_hold(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            path=Path(directory)/'bad.package.json'
            path.write_text(json.dumps({'format':'soc-game-package','version':1,'segments':[],
                'target':{'id':'de2-115-fixed-v1','runtime_abi':1,'required_features':['textures']}}))
            with self.assertRaisesRegex(ValueError,'cannot provide'):load_game.package_segments(path)

    def test_target_version_and_required_features(self):
        for value in (True,2):
            req=copy.deepcopy(self.room['target']);req['runtime_abi']=value
            with self.assertRaises(ValueError):target_capabilities.validate(req)
        scene=copy.deepcopy(self.room);scene['target']['required_features']=[]
        with self.assertRaisesRegex(ValueError,'Declare all features'):portable_game.compile_scene(scene)

    def test_native_default_port_executes_generated_scene(self):
        compiled=portable_game.compile_scene(self.room)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            out=Path(directory);(out/'portable_data.h').write_text(portable_game.header(*compiled))
            (out/'fixture.c').write_text('''#include "game_port.h"
#include "player.h"
extern volatile player_t game_player;
int gfx_view_matrix(const short *v) {(void)v;return 0;}
int gfx_begin_frame(unsigned f) {(void)f;return 0;}
int gfx_draw_mesh(unsigned char h,short x,short y,short z) {(void)h;(void)x;(void)y;(void)z;return 0;}
int gfx_end_frame(void) {return 0;}
void state(player_t *p) {p->x=game_player.x;p->y=game_player.y;p->z=game_player.z;p->grounded=game_player.grounded;}
''')
            dll=out/('port.dll' if os.name=='nt' else 'port.so')
            flags=['-shared','-O1','-Wall','-Wextra','-Werror','-I'+str(out),'-I'+str(ROOT/'firmware/include')]
            if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry']+['-Wl,/export:'+s for s in ('game_port_init','game_port_update','game_port_render','state')]
            else:flags+=['-fPIC']
            subprocess.run([shutil.which('clang'),*flags,str(out/'fixture.c'),str(ROOT/'firmware/ports/scene_explorer.c'),
                str(ROOT/'firmware/src/portable_assets.c'),str(ROOT/'firmware/src/player.c'),str(ROOT/'firmware/src/first_person.c'),'-o',str(dll)],check=True)
            lib=c.CDLL(str(dll));lib.game_port_update.argtypes=[c.c_uint32];lib.state.argtypes=[c.POINTER(Player)]
            try:
                self.assertEqual(lib.game_port_init(),0);lib.game_port_update(4);p=Player();lib.state(c.byref(p))
                self.assertEqual((p.x,p.y,p.z,p.grounded),(0,0,12,1));lib.game_port_update(16);lib.state(c.byref(p))
                self.assertGreater(p.y,0);self.assertFalse(p.grounded);self.assertEqual(lib.game_port_render(1),0)
            finally:
                if os.name=='nt':
                    from _ctypes import FreeLibrary
                    FreeLibrary(lib._handle)

    def test_built_examples_and_generic_quake_use_same_contract(self):
        names=('portable-room','portable-custom','portable-quake')
        for name in names:
            path=linked_test_packages()/(name+'-sdram.package.json')
            spec=json.loads(path.read_text());self.assertEqual(spec['app'],'portable')
            self.assertEqual(spec['content']['runtime_abi'],1);target_capabilities.validate(spec['target'])
            self.assertEqual(len(load_game.package_segments(path)),2)

    def test_custom_module_floating_point_is_rejected_by_cpu_audit(self):
        from rv32i_subset import check
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            source=Path(directory)/'float_port.c'
            source.write_text('int game_port_init(void) { volatile float x=1.5f; return x>1.0f; }')
            with self.assertRaisesRegex(ValueError,'unsupported numeric type|Floating-point constant'):
                check(source)

    def test_generic_obj_adapter_and_explicit_texture_rejection(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            out=Path(directory);obj=out/'floor.obj';dest=out/'scene.json'
            obj.write_text('v -4 0 -4\nv 4 0 -4\nv 4 0 4\nv -4 0 4\nf 1 4 3\nf 1 3 2\n')
            portable_game.export_obj(obj,dest,'portable-obj',2048,[0,0,0])
            _,_,_,compiled,_,_=portable_game.project(out/'scene.project.json')
            self.assertEqual(compiled[-1]['source_triangles'],2)
            obj.write_text('mtllib floor.mtl\n'+obj.read_text())
            (out/'floor.mtl').write_text('newmtl floor\nmap_Kd floor.png\n')
            with self.assertRaisesRegex(ValueError,'unsupported textures'):
                portable_game.export_obj(obj,dest,'portable-obj',2048,[0,0,0])

if __name__=='__main__':unittest.main()
