"""Deterministic command replay preparation using production terrain/controller C.
Scope: shared-world terrain, player collision and explicit camera matrices; not
an entire source-game engine or skeletal animation. No physical board writes.
"""
import argparse,binascii,ctypes as c,hashlib,json,os,shutil,struct,subprocess
from pathlib import Path
import world_assets
ROOT=Path(__file__).resolve().parents[1]
HARNESS=r'''
#include <stdint.h>
#include <stddef.h>
#include "world.h"
#include "gfx_protocol.h"
void *memcpy(void *d,const void *s,size_t n){unsigned char *a=d;const unsigned char *b=s;for(size_t i=0;i<n;++i)a[i]=b[i];return d;}
#define PORTABLE_DATA_DEFINE 1
#include "replay_world.h"
extern volatile uint32_t world_visible_chunks,world_gpu_chunks,world_uploaded_chunks,world_fallback_chunks;
static uint8_t stream[2000000];static uint32_t used;static player_t player;static uint32_t area_index;
static int raw(uint8_t op,const uint8_t *p,uint8_t n){if(used+2u+n>sizeof(stream))return -1;stream[used++]=op;stream[used++]=n;for(uint32_t i=0;i<n;++i)stream[used++]=p[i];return 0;}
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n){return raw(op,p,n);}
static void word(uint8_t *p,int32_t v){p[0]=(uint8_t)((uint16_t)v>>8);p[1]=(uint8_t)v;}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t){uint8_t p[5]={h};word(p+1,v);word(p+3,t);return raw(GFX_OP_DEFINE_MESH,p,5);}
int game_mesh_frame(uint8_t h,const scene_vertex_t *v,uint32_t n){for(uint32_t i=0;i<n;++i){uint8_t p[8]={h,(uint8_t)i};word(p+2,v[i].x);word(p+4,v[i].y);word(p+6,v[i].z);if(raw(GFX_OP_UPLOAD_VERTEX,p,8))return -1;}return 0;}
int gfx_draw_matrix(uint8_t h,const int16_t *m){uint8_t p[25]={h};for(uint32_t i=0;i<12;++i)word(p+1+2*i,m[i]);return raw(GFX_OP_DRAW_MESH,p,25);}
void replay_reset(uint32_t a){area_index=a;used=0;world_select(world_areas+a,&player);}
void replay_step(uint32_t mask,uint32_t ticks){for(uint32_t i=0;i<ticks;++i){world_collision(world_areas+area_index,&player);player_step(&player,world_areas[area_index].physics,mask);}}
int replay_frame(const int16_t *view,uint32_t reserved,uint32_t id){
 used=0;if(world_prepare(world_areas+area_index,&player,view,reserved))return -1;
 uint8_t p[4]={(uint8_t)(id>>24),(uint8_t)(id>>16),(uint8_t)(id>>8),(uint8_t)id};if(raw(GFX_OP_BEGIN_FRAME,p,4))return -1;
 if(world_draw(world_areas+area_index,&player,view,reserved))return -1;return raw(GFX_OP_END_FRAME,p,0);
}
uint32_t replay_size(void){return used;}
const uint8_t *replay_data(void){return stream;}
void replay_state(int32_t *out){const int32_t *p=(const int32_t *)&player;for(uint32_t i=0;i<8;++i)out[i]=p[i];out[8]=(int32_t)world_visible_chunks;out[9]=(int32_t)world_gpu_chunks;out[10]=(int32_t)world_uploaded_chunks;out[11]=(int32_t)world_fallback_chunks;}
'''
def packet(op,p):
 body=bytes((71,70,2,op,len(p)))+p
 return body+struct.pack('>H',binascii.crc_hqx(body,0xffff))
def unpack(raw):
 out=[];i=0
 while i<len(raw):
  op,n=raw[i:i+2];p=raw[i+2:i+2+n];assert len(p)==n;out.append((op,p));i+=2+n
 return out

def prepare(world,route,dest,direct=True,fractional=False):
 scene=json.loads(world.read_text());actors,palette,_,_,report,areas=world_assets.compile_world(scene)
 dest.mkdir(parents=True,exist_ok=True);(dest/'replay_world.h').write_text(world_assets.header(areas))
 src=dest/'harness.c';src.write_text(HARNESS)
 names=['replay_reset','replay_step','replay_frame','replay_size','replay_data','replay_state']
 dll=dest/('replay.dll' if os.name=='nt' else 'replay.so')
 flags=['-shared','-O1','-ffreestanding','-fno-builtin','-Ifirmware/include','-Ifirmware/generated','-I'+str(dest)]
 flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry',*['-Wl,/export:'+n for n in names]] if os.name=='nt' else ['-fPIC']
 flags+=['-DWORLD_FORCE_DIRECT='+str(int(direct))]
 if fractional:flags+=['-DWORLD_GPU_FRACTIONAL=1']
 subprocess.run([shutil.which('clang'),*flags,str(src),'firmware/src/world.c','firmware/src/player.c','-o',str(dll)],cwd=ROOT,check=True)
 lib=c.CDLL(str(dll));lib.replay_data.restype=c.POINTER(c.c_uint8)
 commands=[(4,bytes((i,*rgb))) for i,rgb in enumerate(palette)]
 identity=[256,0,0,0,0,256,0,0,0,0,256,0]
 commands += [(11,struct.pack('>12h',*identity)),(12,struct.pack('>5h',256,256,160,120,257))]
 frames=[];last_area=None
 for index,entry in enumerate(route['frames'],1):
  ai=entry['area'];assert 0<=ai<len(areas)
  if ai!=last_area or entry.get('reset',False):lib.replay_reset(ai);last_area=ai
  ticks=entry.get('ticks',0);mask=entry.get('keys',0)
  if not 0<=ticks<=10000 or not 0<=mask<=31:raise ValueError('Invalid input replay step')
  lib.replay_step(mask,ticks);view=entry['view'];assert len(view)==12
  if lib.replay_frame((c.c_int16*12)(*view),len(actors),index):raise RuntimeError('Production terrain renderer failed')
  raw=c.string_at(lib.replay_data(),lib.replay_size());part=unpack(raw);commands+=part
  state=(c.c_int32*12)();lib.replay_state(state)
  frames.append({'frame':index,'label':entry.get('label',str(index)),'area':areas[ai]['id'],'view':view,'player':list(state)[:8],
   'visible_chunks':state[8],'gpu_chunks':state[9],'uploaded_chunks':state[10],'fallback_chunks':state[11],
   'commands':len(part),'bytes':sum(len(packet(op,p)) for op,p in part)})
 write_input(commands,frames,dest,{'scope':'production shared-world terrain/controller; supplied camera matrices; actors and game-specific transition logic excluded',
  'world_sha256':hashlib.sha256(world.read_bytes()).hexdigest(),'route':route,'direct':direct,'fractional':fractional,'report':report})
 return frames

def write_input(commands,frames,dest,metadata):
 dest.mkdir(parents=True,exist_ok=True);stream=b''.join(packet(op,p) for op,p in commands)
 (dest/'input.hex').write_text(''.join(f'{b:02x}\n' for b in stream));(dest/'input.meta').write_text(f'{len(stream)} {len(frames)}\n')
 (dest/'input.json').write_text(json.dumps({**metadata,'frames':frames,'stream_sha256':hashlib.sha256(stream).hexdigest()},indent=2)+'\n')

def fixtures(dest):
 commands=[(4,bytes((0,80,120,220))),(4,bytes((1,240,0,0))),(4,bytes((2,0,220,0)))]
 cases=[[],[(-4000,-4000,512,0,8000,512,4000,-4000,512,1)],
  [(-100,-80,1024,0,100,1024,100,-80,1024,1),(-100,-80,1024,0,100,1024,100,-80,1024,2)],
  [(-100,-80,1024,0,100,1024,100,-80,1024,1),(-100,-80,512,0,100,512,100,-80,512,2)],
  [(0,0,512,0,0,512,0,0,512,1)],
  [(-100,-100,512,-100,100,512,100,-100,512,1),(100,-100,512,-100,100,512,100,100,512,2)],
  [(-14856,12446,-19861,-32402,-31455,26451,30000,20460,-3533,1)],
  [(-10,-10,30000,0,20,30000,10,-10,30000,1)]*70]
 labels=['empty','viewport','equal-depth-order','occlusion','degenerate','shared-edge','near-crossing','queue-backpressure']
 for i,ts in enumerate(cases,1):
  commands.append((1,struct.pack('>I',i)))
  for t in ts:commands.append((2,struct.pack('>9hB',*t)))
  commands.append((3,b''))
 write_input(commands,[{'frame':i,'label':label} for i,label in enumerate(labels,1)],dest,{'scope':'authored protocol/GPU fixtures'})

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path);p.add_argument('--route',type=Path);p.add_argument('--fixtures',action='store_true');p.add_argument('--gpu',action='store_true');p.add_argument('--fractional',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--simulate',action='store_true');a=p.parse_args()
 if a.fixtures:fixtures(a.out)
 elif a.world and a.route:prepare(a.world,json.loads(a.route.read_text()),a.out,not a.gpu,a.fractional)
 else:p.error('Choose --fixtures or --world and --route')
 if a.simulate:
  active=ROOT/'build/render-replay';active.mkdir(parents=True,exist_ok=True)
  for name in ('input.hex','input.meta'):shutil.copyfile(a.out/name,active/name)
  env=os.environ.copy();env['PATH']=r'C:\intelFPGA\18.1\modelsim_ase\win32aloem'+os.pathsep+env['PATH']
  subprocess.run([__import__('sys').executable,'scripts/soc.py','sim','--full','--simulator','modelsim','--tests','render_frame_replay_tb','--work-dir','build/render-replay/simlib'],cwd=ROOT,env=env,check=True)
  capture=a.out/'capture';capture.mkdir(exist_ok=True)
  for f in active.glob('frame-*'):shutil.copyfile(f,capture/f.name)
  shutil.copyfile(ROOT/'build/render_frame_replay_tb.log',capture/'simulation.log')
 print('Prepared deterministic replay:',a.out)
if __name__=='__main__':main()
