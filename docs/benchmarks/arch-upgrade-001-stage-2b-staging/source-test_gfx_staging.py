"""Independent byte/CRC/tail checks for the measurement-only staging serializer."""
import binascii,ctypes as c,os,random,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class StagingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  out=ROOT/'build/staging-native';out.mkdir(parents=True,exist_ok=True)
  (out/'gfx_staging_input.h').write_text('#define PROBE_FRAMES 1u\n#define PROBE_PREFIX 0u\n#define PROBE_MAX_BYTES 32768u\nstatic const uint8_t replay_input[]={0};\nstatic const uint32_t frame_offsets[]={0},frame_lengths[]={0},frame_ids[]={0},frame_hashes[]={0};\n')
  (out/'harness.c').write_text('''#define main probe_main_unused
#include "firmware/tests/gfx_staging_probe.c"
void reset(void){destination=ram_buffer;staged_word=0;staged_count=0;staged_bytes=0;staged_words=0;}
int append(uint8_t op,const uint8_t *p,uint8_t n){return stage_command(op,p,n);}
void finish(void){if(staged_count){destination[staged_words++]=staged_word;staged_count=0;staged_word=0;}}
const uint8_t *data(void){return (const uint8_t *)ram_buffer;}
uint32_t size(void){return staged_bytes;}
uint32_t words(void){return staged_words;}
''')
  dll=out/'probe.dll';names=('reset','append','finish','data','size','words')
  subprocess.run(['C:/Program Files/LLVM/bin/clang.exe','-shared','-O1','-ffreestanding','-fno-builtin','-nostdlib','-fuse-ld=lld','-Wl,/noentry',*['-Wl,/export:'+n for n in names],'-I.','-Ifirmware/include','-Ifirmware/generated','-I'+str(out),str(out/'harness.c'),'-o',str(dll)],cwd=ROOT,check=True)
  cls.lib=c.CDLL(str(dll));cls.lib.data.restype=c.POINTER(c.c_uint8)
 def append(self,op,p):
  payload=(c.c_uint8*max(1,len(p)))(*p);self.assertEqual(self.lib.append(op,payload,len(p)),0)
  body=b'GF\x02'+bytes((op,len(p)))+p;return body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big')
 def check(self,expected):
  self.lib.finish();self.assertEqual(self.lib.size(),len(expected));self.assertEqual(self.lib.words(),(len(expected)+3)//4);self.assertEqual(c.string_at(self.lib.data(),len(expected)),expected)
 def test_every_length_and_exact_tail(self):
  rng=random.Random(20261011)
  for n in range(256):
   self.lib.reset();self.check(self.append(rng.randrange(256),bytes(rng.randrange(256) for _ in range(n))))
 def test_contiguous_commands_without_padding(self):
  rng=random.Random(0x2b)
  for _ in range(30):
   self.lib.reset();expected=b''
   for _ in range(40):expected+=self.append(rng.randrange(256),bytes(rng.randrange(256) for _ in range(rng.randrange(256))))
   self.check(expected)
if __name__=='__main__':unittest.main()
