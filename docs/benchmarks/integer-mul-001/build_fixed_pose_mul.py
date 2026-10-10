from pathlib import Path
from types import SimpleNamespace
import sys,json
sys.path.insert(0,'scripts');import soc
from rv32i_subset import check
project=json.loads(Path('build/castle/game.project.json').read_text());base=json.loads(Path('build/mario-castle-sdram-direct-profile-detail-mul.package.json').read_text())
sources=[(Path('build/castle')/p).resolve() for p in project['port']['sources']]
flags=['-DWORLD_FORCE_DIRECT=1','-DSOC_PROFILE','-DSOC_PROFILE_DETAIL','-DCASTLE_PROFILE_FIXED_POSE']
check(Path('firmware/ports/castle.c'),'clang',additional_api={'portable_meshes','world_areas','world_select','world_collision','world_floor_contact','world_transition_find','world_prepare','world_draw','world_exit_find','camera_orbit_step','castle_floor_event'},extra_flags=flags)
args=SimpleNamespace(cc='clang',objcopy=None,app='portable',boot=None,use_sdram=True,image_name='mario-castle-fixed-pose-software',extra_flags=flags,port_sources=sources,content=base['content'],target=base['target'])
soc.firmware(args)
args.image_name='mario-castle-fixed-pose-mul';args.extra_flags=flags+['-DSOC_INTEGER_MUL'];soc.firmware(args)
