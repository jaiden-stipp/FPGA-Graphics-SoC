"""Actual firmware byte/CRC equivalence and legacy hardware capability guards."""
import binascii,ctypes as c,json,os,random,shutil,struct,subprocess,unittest
from pathlib import Path
import load_game
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdint.h>
static volatile uint32_t *test_reg(uint32_t offset);
#define SOC_REG(offset) (*test_reg(offset))
#include "firmware/src/gfx.c"
static uint32_t reg,offset_pending,n_pending,writes,free_reads,features;
static uint8_t bytes[512];static uint32_t used;
static void flush(void){if(n_pending){for(uint32_t j=0;j<n_pending;++j)bytes[used++]=(uint8_t)(reg>>(8*j));++writes;n_pending=0;}}
static volatile uint32_t *test_reg(uint32_t offset){
 flush();reg=0;
 if(offset==0){n_pending=1;}
 else if(offset>=0xb0 && offset<=0xbc){n_pending=(offset-0xac)/4;}
 else if(offset==8){++free_reads;reg=free_reads<4?0:256;}
 else if(offset==4)reg=1;
 else if(offset==0x9c)reg=features;
 else if(offset==0xa8)reg=3;
 return &reg;
}
int emit(uint8_t op,const uint8_t *p,uint8_t n,uint32_t f){
 used=0;writes=0;free_reads=0;n_pending=0;features=f;
#ifdef GFX_PACKED
 packed_checked=0;
#endif
 int result=gfx_command(op,p,n);flush();return result;
}
uint32_t size(void){return used;}
uint32_t transactions(void){return writes;}
const uint8_t *data(void){return bytes;}
'''
class PackedFirmwareTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  folder=ROOT/'build/arch-stage2a/native';folder.mkdir(parents=True,exist_ok=True)
  src=folder/'probe.c';src.write_text(HARNESS);cls.libs={}
  for name,extra in [('legacy',[]),('batched',['-DGFX_BATCHED']),('packed',['-DGFX_PACKED'])]:
   dll=folder/(name+('.dll' if os.name=='nt' else '.so'))
   flags=['-shared','-O2','-ffreestanding','-fno-builtin','-I.','-Ifirmware/include','-Ifirmware/generated',*extra]
   flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry',*['-Wl,/export:'+n for n in ('emit','size','transactions','data')]] if os.name=='nt' else ['-fPIC']
   subprocess.run([shutil.which('clang'),*flags,str(src),'-o',str(dll)],cwd=ROOT,check=True)
   lib=c.CDLL(str(dll));lib.data.restype=c.POINTER(c.c_uint8);cls.libs[name]=lib
 def test_all_lengths_crc_order_and_tail_transaction_counts(self):
  rng=random.Random(20261011)
  for n in range(256):
   payload=bytes(rng.randrange(256) for _ in range(n));op=rng.randrange(256)
   body=bytes((71,70,2,op,n))+payload;expected=body+struct.pack('>H',binascii.crc_hqx(body,0xffff))
   buf=(c.c_uint8*max(1,n))(*payload)
   for name,lib in self.libs.items():
    self.assertEqual(lib.emit(op,buf,n,0x80000001),0)
    self.assertEqual(c.string_at(lib.data(),lib.size()),expected,(name,n))
    self.assertEqual(lib.transactions(),(n+10)//4 if name=='packed' else n+7)
 def test_packed_firmware_rejects_legacy_before_emitting(self):
  lib=self.libs['packed'];self.assertEqual(lib.emit(1,(c.c_uint8*1)(0),0,1),-1);self.assertEqual(lib.size(),0)
 def test_loader_old_hardware_check_short_circuits(self):
  class Fake:
   def __init__(self,features,gpu=3):self.features=features;self.gpu=gpu;self.calls=[];self.retries=8
   def operation(self,op,address=0,**kw):self.calls.append(op);return {'cpu_features':self.features,'gpu_features':self.gpu}
  spec={'required_gpu_features':{'packed-enqueue-v1':True}}
  old=Fake(1)
  with self.assertRaises(RuntimeError):load_game.require_hardware(old,spec)
  self.assertEqual(old.calls,[load_game.STATUS]);new=Fake(0x80000001);load_game.require_hardware(new,spec)
  self.assertEqual(new.calls,[load_game.STATUS])
  fraction_only=Fake(0x80000001,1)
  with self.assertRaises(RuntimeError):load_game.require_hardware(fraction_only,spec)

if __name__=='__main__':unittest.main()
