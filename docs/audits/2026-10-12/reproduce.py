from pathlib import Path
import sys,json,ctypes as c
sys.path.insert(0,str(Path.cwd()/'scripts'))
import world_assets,load_game
from test_player import Point
root=Path.cwd();result={}
w=json.loads((root/'build/castle-shaded/world.json').read_text());w['resident_scene']['projection']['focal']=128
compiled=world_assets.compile_world(w)
result['world_projection']={'accepted_camera':compiled[4]['camera'],'cpu_fixed_focal':256,'sample_camera_point':[900,0,1000],'gpu_screen_x_at_128':160+128*900/1000,'cpu_plane_right':-900*256+1000*160,'world_vertex_limit':16000}
class Fake:
    retries=8
    def __init__(self):self.calls=[]
    def operation(self,*a,**kw):self.calls.append(a);return {'cpu_features':0,'gpu_features':0,'input_abi':0}
f=Fake();spec={'required_gpu_features':{'packed-enqueue-v2':True},'required_cpu_features':{'integer-multiply':True}}
load_game.require_hardware(f,spec);result['unknown_features']={'requirements':spec,'accepted':True,'hardware_calls':f.calls}
lib=c.CDLL(str((root/'build/world-tests/edge.dll').resolve()));lib.edge_probe.argtypes=[Point,Point,Point,c.c_int32]
a=(-16000,-16000,-16000);b=(16000,16000,16000);p=(0,0,0)
result['collision_overflow']={'a':a,'b':b,'point':p,'radius':60,'edge_length_squared':sum((x-y)**2 for x,y in zip(a,b)),'expected_hit':1,'actual_hit':lib.edge_probe(Point(*p),Point(*a),Point(*b),60)}
new=json.loads((root/'build/castle-shaded/world.json').read_text());maximum=0
for area in new['areas']:
    v=area['collision']['vertices']
    for t in area['collision']['triangles']:
        for a,b in ((0,1),(1,2),(2,0)):
            maximum=max(maximum,sum((v[t[a]][k]-v[t[b]][k])**2 for k in range(3)))
result['current_castle_max_squared_edge']=maximum
schema=json.loads((root/'schemas/game-package-v1.schema.json').read_text());package=json.loads((root/'build/mario-castle-sdram-direct-packed-mul-geometry-uncapped-interpolated.package.json').read_text())
result['schema']={'additionalProperties':schema['additionalProperties'],'generated_keys_rejected':sorted(set(package)-set(schema['properties'])),'method':'Direct additionalProperties/property-set check; no JSON Schema validator installed'}
(root/'build/repo-audit/contract-reproductions.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('Saved four concrete contract reproductions.')
