"""Counterexamples and contract regressions for all functional audit repairs."""
import copy,ctypes as c,hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'build/test-deps'))
import jsonschema
from referencing import Registry,Resource
import load_game,world_assets,soc,portable_game
from test_support import native_flags,ensure_castle_fixture,linked_test_packages
class AuditTests(unittest.TestCase):
 def test_loader_rejects_bad_types_before_any_hold(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'cpu.bin').write_bytes(b'1234');p=out/'package.json'
   segment={'file':'cpu.bin','address':0,'bytes':4,'sha256':hashlib.sha256(b'1234').hexdigest()}
   for key,value in [('address',0.0),('address',False),('bytes',4.0),('bytes',True),('file',4),('sha256',4)]:
    spec={'format':'soc-game-package','version':1,'segments':[{**segment,key:value}]};p.write_text(json.dumps(spec))
    with self.assertRaises(ValueError):load_game.package_segments(p)
   class Fake:
    retries=1
    def operation(self,*a,**kw):raise AssertionError('Reached FPGA before validation')
   with self.assertRaises(ValueError):load_game.Loader.transfer(Fake(),[(0.0,b'1234','cpu')])
 def test_unknown_or_mistyped_features_never_probe_hardware(self):
  class Fake:
   retries=1
   def operation(self,*a,**kw):raise AssertionError('Unknown requirement reached hardware')
  for kind,name in [('cpu','integer-multiply'),('gpu','packed-enqueue-v2')]:
   with self.assertRaises(ValueError):load_game.require_hardware(Fake(),{'required_'+kind+'_features':{name:True}})
  for kind,name in [('cpu','mul'),('gpu','packed-enqueue-v1')]:
   for value in (1,'true',None):
    with self.assertRaises(ValueError):load_game.require_hardware(Fake(),{'required_'+kind+'_features':{name:value}})
 def test_port_capabilities_have_typed_consistent_declarations(self):
  for port in ({'kind':'custom','render_repeat_safe':'true'}, {'kind':'custom','render_interpolation':True}, {'kind':'scene-explorer','render_repeat_safe':True,'render_interpolation':True}):
   with self.assertRaises(ValueError):portable_game.validate_port_capabilities({'port':port})
  portable_game.validate_port_capabilities({'port':{'kind':'custom','render_repeat_safe':True,'render_interpolation':True}})
 def test_transfer_failure_does_not_release_unverified_memory(self):
  class Fake:
   retries=1
   def __init__(self):self.calls=[]
   def operation(self,op,*a,**kw):
    self.calls.append(op)
    if op==load_game.WRITE:raise TimeoutError('Injected packet loss')
    return {'initialized':True}
  f=Fake()
  with self.assertRaises(TimeoutError):load_game.Loader.transfer(f,[(0,b'1234','cpu')])
  self.assertEqual(f.calls,[load_game.BEGIN,load_game.WRITE])
 def test_world_rejects_projection_disagreement(self):
  original=json.loads((ROOT/'examples/portable-world/world.json').read_text())
  for key,value in [('focal',128),('near_z',512)]:
   scene=copy.deepcopy(original);scene['resident_scene']['projection'][key]=value
   with self.assertRaisesRegex(ValueError,'World runtime requires'):world_assets.compile_world(scene)
 def test_world_rejects_long_diagonal_without_changing_source(self):
  scene=json.loads((ROOT/'examples/portable-world/world.json').read_text());data=scene['areas'][0]['collision'];n=len(data['vertices'])
  data['vertices'] += [[-16000,-16000,-16000],[16000,16000,16000],[-16000,16000,-16000]]
  data['triangles'].append([n,n+1,n+2,data['triangles'][0][3],0])
  if 'triangle_forces' in data:data['triangle_forces'].append(0)
  before=copy.deepcopy(scene)
  with self.assertRaisesRegex(ValueError,'signed 32-bit distance'):world_assets.compile_world(scene)
  self.assertEqual(scene,before)
 def test_castle_retains_all_source_collision_with_new_guard(self):
  scene=json.loads(ensure_castle_fixture(True).read_text());compiled=world_assets.compile_world(scene)
  for original,area in zip(scene['areas'],compiled[5]):
   self.assertEqual(original['collision']['triangles'],area['collision']['triangles'])
   self.assertEqual(original['collision']['vertices'],area['collision']['vertices'])
 def test_legacy_profile_selection_is_independent_of_cached_headers(self):
  with patch('game_assets.generate') as generate:
   for external in (True,False,True):soc.prepare_legacy_assets(SimpleNamespace(use_sdram=external),['mario'])
   self.assertEqual([call.args[0].name for call in generate.call_args_list],['sm64-mario-sdram.json','sm64-mario.json','sm64-mario-sdram.json'])
   custom=ROOT/'profiles/sm64-mario.json';soc.prepare_legacy_assets(SimpleNamespace(use_sdram=True,mario_profile=custom),['mario'])
   self.assertEqual(generate.call_args.args[0],custom)
 def test_package_project_and_world_schemas_match_compiler_contracts(self):
  registry=Registry().with_resources((p.name,Resource.from_contents(json.loads(p.read_text()))) for p in (ROOT/'schemas').glob('*.json'))
  schema=json.loads((ROOT/'schemas/game-package-v1.schema.json').read_text());validator=jsonschema.Draft202012Validator(schema,registry=registry)
  base={'format':'soc-game-package','version':1,'segments':[{'file':'cpu.bin','address':0,'bytes':4,'sha256':'0'*64}]}
  variants=[{}, {'required_cpu_features':{'mul':True,'mmio_feature_bit':0,'geometry-worker-v1':True},'required_gpu_features':{'packed-enqueue-v1':True,'draw-mesh-fraction-v1':True,'mmio_address':0x400000a8,'bit':0},'diagnostic':{'purpose':'test','terrain_submission':'direct'},'cadence':{'simulation_tick_cycles':1666667,'clock_hz':50000000,'render':'uncapped','render_repeat_safe':True,'interpolation':True}}, {'required_gpu_features':{'command-dma-v1':True},'command_buffers':{'address':0x87fe0000,'bytes':2048,'buffer_bytes':1024,'count':2}}]
  for extra in variants:validator.validate({**base,**extra})
  for package in linked_test_packages().glob('*.package.json'):validator.validate(json.loads(package.read_text()))
  with self.assertRaises(jsonschema.ValidationError):validator.validate({**base,'required_gpu_features':{'unknown':True}})
  project_schema=json.loads((ROOT/'schemas/game-project-v1.schema.json').read_text())
  for p in (ROOT/'examples').rglob('game.project.json'):jsonschema.Draft202012Validator(project_schema).validate(json.loads(p.read_text()))
  world_schema=json.loads((ROOT/'schemas/world-ir-v1.schema.json').read_text())
  for p in (ROOT/'examples/portable-world/world.json',ensure_castle_fixture(True)):
   jsonschema.Draft202012Validator(world_schema,registry=registry).validate(json.loads(p.read_text()))
 def test_deployment_selection_checks_hash_and_recorded_capabilities(self):
  import current_deployment
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'profiles').mkdir();(root/'build').mkdir();sof=root/'build/hardware.sof';sof.write_bytes(b'fixture')
   code=root/'build/cpu.bin';code.write_bytes(b'1234');package=root/'build/game.package.json'
   spec={'format':'soc-game-package','version':1,'segments':[{'file':'cpu.bin','address':0,'bytes':4,'sha256':hashlib.sha256(b'1234').hexdigest()}]}
   package.write_text(json.dumps(spec));selection={'hardware':{'file':'build/hardware.sof','sha256':hashlib.sha256(b'fixture').hexdigest(),'cpu_features':0x80000003,'gpu_features':3,'input_abi':0x494e0101},'package':'build/game.package.json'}
   (root/'profiles/current-deployment.json').write_text(json.dumps(selection))
   with patch.object(current_deployment,'ROOT',root):
    current_deployment.selection()
    spec['required_gpu_features']={'command-dma-v1':True};spec['command_buffers']={'address':0x87fe0000,'bytes':2048,'buffer_bytes':1024,'count':2};package.write_text(json.dumps(spec))
    with self.assertRaises(RuntimeError):current_deployment.selection()
    sof.write_bytes(b'changed')
    with self.assertRaisesRegex(ValueError,'hash changed'):current_deployment.selection()
 def test_worker_timeout_and_inactive_results_abort_across_timer_wrap(self):
  out=ROOT/'build/audit-fixes/worker-native';out.mkdir(parents=True,exist_ok=True)
  source=out/'probe.c';source.write_text(r'''
#include <stdint.h>
static uint32_t regs[128],timer;
#define SOC_REG(offset) (*reg_ptr(offset))
static volatile uint32_t *reg_ptr(uint32_t offset){if(offset==0x58){timer+=3;return &timer;}if(offset==0x18c)regs[0x104/4]=0;return &regs[offset/4];}
#define SOC_GEOMETRY_OFFLOAD 1
#define GEOMETRY_TIMEOUT_CYCLES 10u
#include "geometry_worker.h"
int probe(uint32_t start,uint32_t status){
 for(uint32_t i=0;i<128;++i)regs[i]=0;
 timer=start;regs[0x9c/4]=2;regs[0x100/4]=0x47570101;regs[0x104/4]=status;
 regs[0x108/4]=regs[0x10c/4]=1;regs[0x180/4]=123;regs[0x184/4]=234;regs[0x188/4]=1000;
 scene_vertex_t vertex={0};int16_t origin[3]={0},view[12]={0};int32_t position[3]={0};geometry_point_t output;uint8_t code;
 int result=geometry_transform(&vertex,1,origin,position,view,&output,&code);
 if(status&0xff00u)return result==1 && output.x==123 && output.y==234 && output.z==1000?0:-2;
 return result==-1 && regs[0x164/4]==2?0:-1;
}
''')
  dll=out/('probe.dll' if os.name=='nt' else 'probe.so')
  subprocess.run([shutil.which('clang'),*native_flags(['probe']),'-Ifirmware/include',str(source),'-o',str(dll)],cwd=ROOT,check=True)
  lib=c.CDLL(str(dll));lib.probe.argtypes=[c.c_uint32,c.c_uint32]
  for start,status in [(0,0),(0,1),(0xfffffff9,1),(0,2),(0,0x101),(0xfffffff9,0x100)]:self.assertEqual(lib.probe(start,status),0)
if __name__=='__main__':unittest.main()
