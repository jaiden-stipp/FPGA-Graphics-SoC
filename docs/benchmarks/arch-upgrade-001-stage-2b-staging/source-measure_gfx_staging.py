"""Compare actual packed submission with contiguous command-buffer staging."""
import argparse,binascii,hashlib,json,re,struct,subprocess,sys,time
from pathlib import Path
from load_game import Loader,STATUS,BEGIN,package_segments,require_hardware
ROOT=Path(__file__).resolve().parents[1]
FIELDS=('cycles','retired','freezes','bubbles','redirects','writes','busy','hits','misses','fills','bytes','words','hash','error','index','reserved')
def build(source,out):
 out.mkdir(parents=True,exist_ok=True)
 blob=bytes(int(v,16) for v in (source/'input.hex').read_text().split());frames=[];i=0;prefix=None
 while i<len(blob):
  if blob[i:i+3]!=b'GF\x02' or i+7>len(blob):raise ValueError('Malformed trace')
  n=blob[i+4]+7;cmd=blob[i:i+n]
  if len(cmd)!=n or binascii.crc_hqx(cmd[:-2],0xffff)!=int.from_bytes(cmd[-2:],'big'):raise ValueError('Trace CRC/length mismatch')
  if cmd[3]==1:
   if frames and 'length' not in frames[-1]:raise ValueError('Overlapping frame')
   if prefix is None:prefix=i
   frames.append({'offset':i,'id':int.from_bytes(cmd[5:-2],'big')})
  if cmd[3]==3:
   if not frames or 'length' in frames[-1]:raise ValueError('Unpaired frame end')
   frames[-1]['length']=i+n-frames[-1]['offset']
  i+=n
 if not frames or any('length' not in f for f in frames):raise ValueError('Incomplete trace')
 def fold(data):
  h=0
  for b in data:h=(31*h+b)&0xffffffff
  return h
 for f in frames:f['hash']=fold(blob[f['offset']:f['offset']+f['length']])
 max_bytes=max(f['length'] for f in frames)
 if max_bytes>0xf000:raise ValueError('Trace exceeds isolated SDRAM scratch space')
 header=f'#define PROBE_FRAMES {len(frames)}u\n#define PROBE_PREFIX {prefix}u\n#define PROBE_MAX_BYTES {max_bytes}u\n'
 header+='static const uint8_t replay_input[]={'+','.join(str(v) for v in blob)+'};\n'
 for key in ('offset','length','id','hash'):header+='static const uint32_t frame_'+({'offset':'offsets','length':'lengths','id':'ids','hash':'hashes'}[key])+'[]={'+','.join(str(f[key])+'u' for f in frames)+'};\n'
 (out/'gfx_staging_input.h').write_text(header)
 llvm=Path('C:/Program Files/LLVM/bin');elf=out/'probe.elf'
 cmd=[str(llvm/'clang.exe'),'--target=riscv32-unknown-elf','-fuse-ld=lld','-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax','-O1','-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Ifirmware/include','-Ifirmware/generated','-I'+str(out),'-Wl,-T,firmware/link.ld','-Wl,--no-relax','-Wl,--gc-sections','-Wl,-Map,'+str(out/'probe.map'),'firmware/start.S','firmware/tests/gfx_staging_probe.c','-o',str(elf)]
 subprocess.run(cmd,cwd=ROOT,check=True);subprocess.run([str(llvm/'llvm-objcopy.exe'),'-O','binary',str(elf),str(out/'probe.bin')],check=True)
 nm=subprocess.check_output([str(llvm/'llvm-nm.exe'),'--defined-only',str(elf)],text=True)
 syms={m[3]:int(m[1],16) for line in nm.splitlines() if (m:=re.fullmatch(r'([0-9a-fA-F]+)\s+(\w)\s+(\S+)',line))}
 dis=subprocess.check_output([str(llvm/'llvm-objdump.exe'),'-d',str(elf)],text=True);(out/'probe-disassembly.txt').write_text(dis)
 for line in dis.splitlines():
  m=re.match(r'\s*[0-9a-f]+:\s+((?:[0-9a-f]{2} ){3}[0-9a-f]{2})',line)
  if m:
   ins=int.from_bytes(bytes.fromhex(m[1]),'little')
   if ins&0x7f==0x33 and ins>>25==1:raise ValueError('Probe unexpectedly emits M instructions')
 (out/'probe.symbols.json').write_text(json.dumps(syms,indent=2)+'\n')
 data=(out/'probe.bin').read_bytes();spec={'format':'soc-game-package','version':1,'required_gpu_features':{'packed-enqueue-v1':True},'segments':[{'file':'probe.bin','address':0,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
 (out/'probe.package.json').write_text(json.dumps(spec,indent=2)+'\n')
 report={'scope':'Recorded terrain command serialization; no transforms/actors/game update; packed enqueue excludes GPU drain, staging excludes verification and hypothetical DMA transfer. Same CRC, continuous buffer without per-command padding. RAM input isolates destination stores.','source':str(source.resolve()),'source_sha256':hashlib.sha256(blob).hexdigest(),'frames':frames,'prefix_bytes':prefix,'max_bytes':max_bytes,'symbols':syms,'compile_command':cmd,'probe_sha256':spec['segments'][0]['sha256'],'staging_address':0x87ff0000,'clock_hz':50000000}
 (out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print('Built staging probe:',[f['length'] for f in frames],flush=True);return report

def collect(out,restore,trials):
 config=json.loads((out/'build.json').read_text());syms=config['symbols'];candidate=package_segments(out/'probe.package.json');baseline=package_segments(restore)
 loader=Loader();report={'scope':config['scope'],'build':config,'trials':[],'restore':str(restore.resolve())}
 try:require_hardware(loader,json.loads((out/'probe.package.json').read_text()))
 except Exception:
  loader.close();raise
 if any(addr>=0x80000000 and addr+len(data)>0x87ff0000 for addr,data,_ in baseline):
  loader.close();raise ValueError('Restore assets overlap the reserved staging scratch')
 try:
  for trial in range(trials):
   loader.transfer(candidate);deadline=time.monotonic()+30
   while time.monotonic()<deadline:
    status=loader.operation(STATUS)
    if status['scratch']&0xffff0000==0xdead0000:raise RuntimeError('Probe failed '+str(status))
    if status['scratch']==0x2b00600d:break
    time.sleep(.02)
   else:raise TimeoutError('Probe did not complete')
   loader.operation(BEGIN);n=len(config['frames'])*3*16;words=[]
   for j in range(0,n,3):words.extend(loader.operation(3,syms['staging_results']+j*4,count=min(3,n-j))['words'][:min(3,n-j)])
   clock=loader.operation(3,syms['staging_clock'],count=1)['words'][0]
   if clock!=50000000:raise RuntimeError('Unexpected clock')
   results=[dict(zip(FIELDS,words[j:j+16])) for j in range(0,n,16)]
   for f,frame in enumerate(config['frames']):
    for mode in range(3):
     r=results[f*3+mode];assert not r['error'] and r['index']==f*3+mode and r['bytes']==frame['length']
     if mode:assert r['hash']==frame['hash'] and r['words']==(frame['length']+3)//4
     if mode==2:assert r['writes']==r['words']
   report['trials'].append({'trial':trial+1,'results':results,'done_status':status});(out/'physical.json').write_text(json.dumps(report,indent=2)+'\n');print('trial',trial+1,[(r['cycles'],r['freezes'],r['writes']) for r in results],flush=True)
 except Exception as exc:report['failure']=repr(exc);raise
 finally:
  try:
   # The probe only writes its isolated high SDRAM scratch; game assets remain immutable.
   loader.transfer([seg for seg in baseline if seg[0]<65536]);time.sleep(2)
   status=loader.operation(STATUS);assert status['initialized'] and not status['held'] and 0<status['scratch']<0x10000000
   report['restored_status']=status
  finally:loader.close();(out/'physical.json').write_text(json.dumps(report,indent=2)+'\n')
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,default=ROOT/'build/arch-stage2a/castle-packed');p.add_argument('--out',type=Path,default=ROOT/'build/arch-stage2b-staging');p.add_argument('--collect',action='store_true');p.add_argument('--trials',type=int,default=3);p.add_argument('--restore',type=Path,default=ROOT/'build/mario-castle-sdram-direct-packed-mul.package.json');a=p.parse_args()
 if not 1<=a.trials<=10:p.error('trials must be 1..10')
 build(a.input,a.out)
 if a.collect:collect(a.out,a.restore,a.trials)
if __name__=='__main__':main()
