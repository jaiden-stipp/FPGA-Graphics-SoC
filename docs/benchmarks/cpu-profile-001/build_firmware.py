import sys,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,'scripts');import soc
base=json.loads(Path('build/cpu-profile/baseline/mario-castle-sdram-direct.package.json').read_text())
project=json.loads(Path('build/castle/game.project.json').read_text())
sources=[(Path('build/castle')/p).resolve() for p in project['port']['sources']]
args=SimpleNamespace(cc='clang',objcopy=None,app='portable',boot=None,use_sdram=True,image_name='mario-castle-profile',extra_flags=['-DWORLD_FORCE_DIRECT=1','-DSOC_PROFILE'],port_sources=sources,content=base['content'],target=base['target'])
soc.firmware(args)
args.image_name='mario-castle-profile-batched';args.extra_flags+=['-DGFX_BATCHED'];soc.firmware(args)
assert Path('build/mario-castle-profile.assets.bin').read_bytes()==Path('build/cpu-profile/baseline/mario-castle-sdram-direct.assets.bin').read_bytes()
print('PASS identical game asset bytes')
