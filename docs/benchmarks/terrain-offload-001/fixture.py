from pathlib import Path
from types import SimpleNamespace
import sys,json,time
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts'))
import soc,portable_game
from profile_cpu import collect
from load_game import Loader,package_segments,STATUS
out=root/'build/terrain-offload/fixture';out.mkdir(parents=True,exist_ok=True)
resident=json.loads((root/'examples/custom-port/scene.json').read_text())
resident['meshes']=[m for m in resident['meshes'] if m['role']=='actor']
resident['projection']['focal']=256
vertices=[[5*x-20,5*y-40,400] for y in range(16) for x in range(8)]
triangles=[]
for y in range(15):
 for x in range(7):
  a=8*y+x;triangles.extend([[a,a+8,a+9,1],[a,a+9,a+1,2]])
scene={'format':'soc-world-ir','version':1,'resident_scene':resident,'areas':[{'id':'bounded-grid','spawn':[0,0,0],'vertices':vertices,'triangles':triangles,'collision':{'vertices':[[-100,0,-100],[100,0,-100],[0,0,100]],'triangles':[[0,2,1,'floor',0]]}}]}
(out/'world.json').write_text(json.dumps(scene,indent=2)+'\n')
(out/'port.c').write_text('''#include "soc.h"
#include "gfx.h"
#include "world.h"
#include "portable_data.h"
static player_t player;
volatile player_t game_player;
static const int16_t view[12]={256,0,0,0,0,256,0,0,0,0,256,0};
int game_port_init(void){world_select(world_areas,&player);game_player=player;return 0;}
void game_port_update(uint32_t input){(void)input;}
int game_port_render(uint32_t frame){
    if(world_prepare(world_areas,&player,view,PORTABLE_MESH_COUNT) || gfx_identity_view() || gfx_begin_frame(frame))return -1;
    if(world_draw(world_areas,&player,view,PORTABLE_MESH_COUNT))return -1;
    return gfx_end_frame();
}
''')
project={'format':'soc-game-project','version':1,'name':'gpu-admission-fixture','scene':'world.json','port':{'kind':'custom','sources':['port.c','../../../firmware/src/world.c','../../../firmware/src/game_services.c'],'exports':['world_areas','world_select','world_prepare','world_draw','player_bind_query','player_floor_index']}}
project_path=out/'game.project.json';project_path.write_text(json.dumps(project,indent=2)+'\n')
stems={}
try:
 for label,direct,fine,detail in [('restore',False,False,False),('fixture-direct',True,False,True),('fixture-safe',False,False,True),('fixture-fine-safe',False,True,True)]:
  args=SimpleNamespace(project=project_path,cc='clang',objcopy=None,terrain_direct=direct,terrain_gpu_safe=not direct,profile_fine=fine,profile_detail=detail,cpu_profile=detail,integer_mul=True,batch_gfx=False)
  soc.portable_package(args)
  stems[label]='gpu-admission-fixture-sdram'+('-direct' if direct else '-gpu-safe')+('-profile-detail' if detail else '')+('-fine' if fine else '')+'-mul'
finally:
 # Restore generated source headers even if a fixture build fails.
 portable_game.generate(root/'build/castle/game.project.json')
restore=root/'build'/(stems['restore']+'.package.json')
try:
 for label in ('fixture-direct','fixture-safe','fixture-fine-safe'):
  stem=stems[label];print('BEGIN',label,flush=True)
  collect(root/'build'/(stem+'.package.json'),root/'build'/(stem+'.symbols.json'),restore,root/'build/terrain-offload'/(label+'.json'),trials=3,reuse_immutable_assets=True)
finally:
 loader=Loader()
 try:
  loader.transfer(package_segments(root/'build/mario-castle-sdram-direct-mul.package.json'))
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   status=loader.operation(STATUS)
   if not status['held'] and 0<status['scratch']<0x10000000:break
   time.sleep(.05)
  else:raise RuntimeError('Mario did not resume')
  a=status;time.sleep(.3);b=loader.operation(STATUS);assert b['scratch']>a['scratch']
  (root/'build/terrain-offload/restored-mario.json').write_text(json.dumps({'first':a,'second':b},indent=2)+'\n')
 finally:loader.close()
