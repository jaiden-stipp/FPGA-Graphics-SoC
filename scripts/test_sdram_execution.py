"""Executable package contracts and backward-compatible capability preflight."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
import load_game
from sdram_execution import validate_execution
ROOT=Path(__file__).resolve().parents[1]
class ExecutionPackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'package.json'
  records=[]
  for name,address,data in [('boot.bin',0,b'boot'),('code.bin',0x80000000,b'codecode'),('state.bin',0x81000000,b'data'),('assets.bin',0x81000020,b'mesh')]:
   (self.root/name).write_bytes(data);records.append({'file':name,'address':address,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  self.spec={'format':'soc-game-package','version':1,'segments':records,'required_cpu_features':{'sdram-exec-v1':True},'execution':{'abi':'local-boot-sdram-v1','entry':0x80000000,'code_address':0x80000000,'code_bytes':8,'bss_address':0x81000004,'bss_bytes':4}}
 def tearDown(self):self.tmp.cleanup()
 def parse(self,spec=None):
  self.path.write_text(json.dumps(spec or self.spec));return load_game.package_segments(self.path)
 def test_valid_layout(self):self.assertEqual(len(self.parse()),4)
 def test_old_packages_unchanged(self):
  s=copy.deepcopy(self.spec);s.pop('execution');s.pop('required_cpu_features');self.assertEqual(len(self.parse(s)),4)
 def test_feature_and_metadata_required_together(self):
  for key in ('execution','required_cpu_features'):
   s=copy.deepcopy(self.spec);s.pop(key)
   with self.assertRaises(ValueError):self.parse(s)
  s=copy.deepcopy(self.spec);s.pop('required_cpu_features');s['execution']=None
  with self.assertRaises(ValueError):self.parse(s)
 def test_invalid_entry_and_window(self):
  for key,value in [('entry',0),('entry',0x80000008),('entry',0x80000001),('code_address',0x80000004),('code_bytes',16),('bss_address',0x80000000),('bss_bytes',True),('abi','other')]:
   s=copy.deepcopy(self.spec);s['execution'][key]=value
   with self.assertRaises(ValueError):self.parse(s)
 def test_bss_cannot_overlap_loaded_data(self):
  s=copy.deepcopy(self.spec);s['execution']['bss_address']=0x81000000
  with self.assertRaises(ValueError):self.parse(s)
 def test_no_other_immutable_segments(self):
  s=copy.deepcopy(self.spec);s['segments'][-1]['address']=0x80000020
  with self.assertRaises(ValueError):self.parse(s)
 def test_preflight_rejects_old_hardware_before_hold(self):
  class Board:
   retries=1
   def __init__(self,bits):self.bits=bits;self.calls=[]
   def operation(self,op,**kw):self.calls.append(op);return {'cpu_features':self.bits}
  old=Board(0x80000003)
  with self.assertRaises(RuntimeError):load_game.require_hardware(old,self.spec)
  self.assertEqual(old.calls,[load_game.STATUS])
  new=Board(0x80000007);load_game.require_hardware(new,self.spec);self.assertEqual(new.calls,[load_game.STATUS])
 def test_schema_agrees(self):
  sys.path.insert(0,str(ROOT/'build/test-deps'));import jsonschema
  jsonschema.validate(self.spec,json.loads((ROOT/'schemas/game-package-v1.schema.json').read_text()))
if __name__=='__main__':unittest.main()
