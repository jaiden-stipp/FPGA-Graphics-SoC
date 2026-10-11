"""Actual DMA driver serialization, tails, ownership and host preflight guards."""
import binascii, ctypes as c, json, random, subprocess, unittest
from pathlib import Path
import load_game
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdint.h>
static volatile uint32_t *reg_ptr(uint32_t offset);
static uint32_t buffers[2][256], regs[64], pending, used, descriptors, features;
static uint8_t wire[200000];
#define SOC_REG(offset) (*reg_ptr(offset))
#define GFX_DMA_BUFFER(index) buffers[index]
#define GFX_DMA 1
#include "firmware/src/gfx.c"
static volatile uint32_t *reg_ptr(uint32_t offset) {
 if(pending) {
  uint32_t index=(regs[0xc4/4]-0x87fe0000u)/1024u, n=regs[0xc8/4];
  if(index>1 || n>1024 || used+n>200000)regs[0xd4/4]=2;
  else {
   const uint8_t *p=(const uint8_t *)buffers[index];
   for(uint32_t i=0;i<n;++i)wire[used++]=p[i];
   regs[0xd4/4]=0;regs[0xd8/4]=regs[0xcc/4];++descriptors;
  }
  pending=0;
 }
 if(offset==0xd0)pending=1;
 return &regs[offset/4];
}
void reset(uint32_t capability) {
 for(uint32_t i=0;i<64;++i)regs[i]=0;
 features=capability;regs[0x9c/4]=0x80000001u;regs[0xa8/4]=features;regs[0xc0/4]=0x444d0101;
 pending=used=descriptors=0;
 dma_checked=dma_buffer=dma_size=dma_word=dma_count=dma_words=dma_sequence=dma_active=0;
}
void old_error(void){regs[0xd4/4]=0x102u;}
int append(uint8_t op,const uint8_t *p,uint8_t n){return gfx_command(op,p,n);}
int finish(void){if(dma_publish())return -1;return dma_wait();}
const uint8_t *data(void){return wire;}
uint32_t size(void){return used;}
uint32_t chunks(void){return descriptors;}
'''
class DmaTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  out=ROOT/'build/dma-native';out.mkdir(parents=True,exist_ok=True)
  src=out/'harness.c';src.write_text(HARNESS);dll=out/'driver.dll'
  names=('reset','append','finish','data','size','chunks','old_error')
  subprocess.run(['C:/Program Files/LLVM/bin/clang.exe','-shared','-O1','-ffreestanding','-fno-builtin','-nostdlib','-fuse-ld=lld','-Wl,/noentry',*['-Wl,/export:'+n for n in names],'-I.','-Ifirmware/include','-Ifirmware/generated',str(src),'-o',str(dll)],cwd=ROOT,check=True)
  cls.lib=c.CDLL(str(dll));cls.lib.data.restype=c.POINTER(c.c_uint8)
 def append(self,op,p):
  payload=(c.c_uint8*max(1,len(p)))(*p)
  self.assertEqual(self.lib.append(op,payload,len(p)),0)
  body=b'GF\x02'+bytes((op,len(p)))+p
  return body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big')
 def test_lengths(self):
  rng=random.Random(0x2b)
  for n in range(256):
   self.lib.reset(7);expected=self.append(2,bytes(rng.randrange(256) for _ in range(n)))
   self.assertEqual(self.lib.finish(),0)
   self.assertEqual(c.string_at(self.lib.data(),self.lib.size()),expected)
 def test_command_crossings_and_end_frame(self):
  rng=random.Random(20261011)
  for _ in range(25):
   self.lib.reset(7);expected=b''
   for _ in range(60):expected+=self.append(2,bytes(rng.randrange(256) for _ in range(rng.randrange(256))))
   expected+=self.append(3,b'');self.assertEqual(self.lib.finish(),0)
   self.assertEqual(c.string_at(self.lib.data(),self.lib.size()),expected)
   self.assertEqual(self.lib.chunks(),(len(expected)+1023)//1024)
 def test_capability_rejected_without_submission(self):
  self.lib.reset(3);self.assertEqual(self.lib.append(3,None,0),-1);self.assertEqual(self.lib.size(),0)
 def test_recovery_from_previous_descriptor_error(self):
  self.lib.reset(7);self.lib.old_error();expected=self.append(3,b'')
  self.assertEqual(self.lib.finish(),0)
  self.assertEqual(c.string_at(self.lib.data(),self.lib.size()),expected)
 def test_loader_gate_before_begin(self):
  class Fake:
   retries=1
   def operation(self,op,**kwargs):
    self.last=op;return {'cpu_features':0x80000001,'gpu_features':3}
  f=Fake()
  with self.assertRaises(RuntimeError):load_game.require_hardware(f,{'required_gpu_features':{'command-dma-v1':True}})
  self.assertEqual(f.last,load_game.STATUS)
 def test_buffer_overlap_rejected(self):
  source=ROOT/'build/mario-castle-sdram-direct-dma-mul.package.json'
  if not source.exists():self.skipTest('Build DMA package first')
  spec=json.loads(source.read_text());spec['segments'][1]['address']=0x87fe0004-spec['segments'][1]['bytes']
  path=source.parent/'dma-overlap-test.package.json';path.write_text(json.dumps(spec))
  try:
   with self.assertRaisesRegex(ValueError,'overlaps command'):load_game.package_segments(path)
  finally:path.unlink()
if __name__=='__main__':unittest.main()
