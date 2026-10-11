"""Independent arithmetic, source-preservation and legacy capability checks."""
import ctypes as c,importlib.util,json,os,random,shutil,subprocess,unittest
from pathlib import Path
import load_game,world_assets
from test_terrain_offload import HARNESS
ROOT=Path(__file__).resolve().parents[1]
class FractionalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  out=ROOT/'build/fractional-tests';out.mkdir(parents=True,exist_ok=True)
  source=out/'probe.c';source.write_text(HARNESS.replace('WORLD_SOURCE',(ROOT/'firmware/src/world.c').as_posix()))
  dll=out/('probe.dll' if os.name=='nt' else 'probe.so')
  flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated','-DWORLD_GPU_FRACTIONAL=1','-DWORLD_GPU_CAPABLE=1']
  flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/export:admission_probe','-Wl,/export:transform_probe'] if os.name=='nt' else ['-fPIC']
  subprocess.run([shutil.which('clang'),*flags,str(source),'firmware/src/player.c','-o',str(dll)],cwd=ROOT,check=True);cls.lib=c.CDLL(str(dll))
 def test_fractional_admission_matches_single_floor_reference(self):
  rng=random.Random(1209);accepted=0;fractional=0
  for _ in range(1200):
   origin=[rng.randrange(-200,201),rng.randrange(-100,101),rng.randrange(400,801)];position=[rng.randrange(-50,51) for j in range(3)]
   view=[256,rng.randrange(-20,21),0,0,0,237,98,-100,0,-98,237,300]
   bounds=[v for j in range(3) for v in (origin[j]-15,origin[j]+15)];m=(c.c_int16*12)()
   yes=self.lib.admission_probe((c.c_int16*3)(*origin),(c.c_int16*6)(*bounds),(c.c_int32*3)(*position),(c.c_int16*12)(*view),m)
   if not yes:continue
   accepted+=1
   sums=[sum((origin[j]-position[j])*4*view[4*r+j] for j in range(3)) for r in range(3)]
   fractional+=any(v%256 for v in sums)
   for i in range(8):
    point=[bounds[2*j+((i>>j)&1)] for j in range(3)];local=[point[j]-origin[j] for j in range(3)];cpu=(c.c_int32*3)()
    self.lib.transform_probe((c.c_int32*3)(*point),(c.c_int32*3)(*position),(c.c_int16*12)(*view),cpu)
    gpu=[(sum(local[j]*m[4*r+j] for j in range(3))+sums[r]%256)//256+m[4*r+3] for r in range(3)]
    self.assertEqual(list(cpu),gpu)
  self.assertGreater(accepted,100);self.assertGreater(fractional,100)
 def test_source_faces_and_order_preserved_by_tighter_packing(self):
  spec=importlib.util.spec_from_file_location('baseline_world_assets',ROOT/'docs/benchmarks/arch-upgrade-001-stage-0/baseline-world_assets.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
  scene=json.loads((ROOT/'build/castle/world.json').read_text())
  def expand(chunks):
   return [(i,tuple(tuple(p[j]+ch['origin'][j] for j in range(3)) for p in (ch['vertices'][t[k]] for k in range(3))),t[3]) for ch in chunks for i,t in zip(ch['source_triangles'],ch['triangles'])]
  for area in scene['areas']:
   args=(area['vertices'],area['triangles'],area.get('triangle_room_masks'));before=old.chunks(*args);after=world_assets.chunks(*args,tight=True)
   self.assertEqual(before,world_assets.chunks(*args))
   balanced=world_assets.chunks(*args,tight=True,min_faces=32)
   self.assertEqual(expand(before),expand(balanced))
   self.assertEqual(expand(before),expand(after));self.assertEqual(len(expand(after)),len(area['triangles']))
   self.assertTrue(all(len(ch['vertices'])<=128 and len(ch['triangles'])<=256 for ch in after))
 def test_old_hardware_rejected_without_reading_unsupported_address(self):
  class Fake:
   def __init__(self,features):self.calls=[];self.features=features;self.retries=8
   def operation(self,op,address=0,**kw):self.calls.append(op);return {'cpu_features':self.features,'gpu_features':1}
  package={'required_gpu_features':{'draw-mesh-fraction-v1':True}}
  old=Fake(1)
  with self.assertRaises(RuntimeError):load_game.require_hardware(old,package)
  self.assertEqual(old.calls,[load_game.STATUS]);new=Fake(0x80000001);load_game.require_hardware(new,package);self.assertEqual(new.calls,[load_game.STATUS])
if __name__=='__main__':unittest.main()
