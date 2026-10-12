"""Pinned, isolated fixtures and platform-correct native library flags."""
import hashlib,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(os.environ.get('SOC_TEST_FIXTURES',str(ROOT/'build/test-fixtures'))).resolve()
if not FIXTURES.is_relative_to((ROOT/'build').resolve()):raise ValueError('Test fixtures must stay under repository build/')

def native_flags(exports):
    flags=['-shared','-O1','-ffreestanding','-fno-builtin']
    if os.name=='nt':flags+=['-fuse-ld=lld','-nostdlib','-Wl,/noentry',*['-Wl,/export:'+n for n in exports]]
    else:flags+=['-fPIC']
    return flags

def ensure_castle_fixture(shaded=False):
    from sm64_subset import fetch
    from sm64_castle import export
    fetch() # Enforce the pin/cleanliness even with cached fixture data.
    inputs=['sm64.lock.json','profiles/sm64-castle-colors.json','profiles/sm64-mario-sdram.json',
        'scripts/sm64_castle.py','scripts/sm64_subset.py','scripts/animation_assets.py','scripts/scene_assets.py','scripts/game_assets.py']
    signature=hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in inputs)+bytes([shaded])).hexdigest()
    folder=FIXTURES/('castle-shaded' if shaded else 'castle-legacy')
    stamp=folder/'fixture.json';world=folder/'world.json'
    if stamp.exists() and world.exists():
        old=json.loads(stamp.read_text(encoding='utf-8'))
        if old.get('inputs')==signature and old.get('world_sha256')==hashlib.sha256(world.read_bytes()).hexdigest() and all((ROOT/p).exists() and hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in old.get('headers',{}).items()):return world
    export(folder,shade=shaded)
    names=['firmware/generated/castle_actor_data.h','firmware/generated/castle_transitions.h','firmware/generated/castle_surface_types.h']
    stamp.write_text(json.dumps({'inputs':signature,'world_sha256':hashlib.sha256(world.read_bytes()).hexdigest(),'headers':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names}},indent=2)+'\n',encoding='utf-8')
    return world


def linked_test_packages():
    """Build isolated linked packages instead of reading a developer's old outputs."""
    import argparse,subprocess,sys
    import soc,quake_assets,quake_demo
    folder=FIXTURES/'packages';folder.mkdir(parents=True,exist_ok=True)
    pak=quake_assets.fetch_shareware()
    quake_assets.generate(ROOT/'profiles/quake-e1m1.json',pak)
    quake_demo.emit(pak,ROOT/'build/quake-interactive')
    inputs=[*ROOT.glob('*.lock.json'),* (ROOT/'scripts').glob('*.py'),*(ROOT/'firmware').rglob('*.c'),*(ROOT/'firmware/include').glob('*.h'),*(ROOT/'profiles').glob('*.json')]
    # Generated data is reproduced above; do not key on unrelated global headers.
    signature=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(inputs))+pak.read_bytes()+subprocess.check_output([shutil.which('clang'),'--version'])).hexdigest()
    stamp=folder/'linked-fixtures.json'
    if stamp.exists():
        from load_game import package_segments
        old=json.loads(stamp.read_text(encoding='utf-8'))
        if old.get('inputs')==signature:
            try:
                for name in old['packages']:package_segments(folder/(name+'.package.json'))
                return folder
            except (ValueError,OSError):pass
    def save(name,stem):
        spec=json.loads((ROOT/'build'/(stem+'.package.json')).read_text(encoding='utf-8'))
        for segment in spec['segments']:shutil.copyfile(ROOT/'build'/segment['file'],folder/segment['file'])
        (folder/(name+'.package.json')).write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
    def args(app,stem,content):
        return argparse.Namespace(cc='clang',objcopy=None,app=app,boot=None,image_name=stem,use_sdram=True,extra_flags=[],content=content)
    mario=ROOT/'profiles/sm64-mario-sdram.json'
    from game_assets import generate
    from game_package import mario_content
    generate(mario);content=mario_content(mario,json.loads((ROOT/'build/game/conversion.json').read_text()))
    a=args('mario','test-fixture-mario-sdram',content);a.mario_profile=mario;soc.firmware(a);save('mario-sdram',a.image_name)
    content=quake_assets.generate(ROOT/'profiles/quake-e1m1.json',pak)
    a=args('quake','test-fixture-quake-sdram',content);soc.firmware(a);save('quake-sdram',a.image_name)
    portable_quake=folder/'quake.scene.json'
    import portable_game
    portable_game.export_quake(pak,ROOT/'profiles/quake-e1m1.json',portable_quake)
    packages=['mario-sdram','quake-sdram']
    for name,path in [('portable-room',ROOT/'examples/portable-room/game.project.json'),('portable-custom',ROOT/'examples/custom-port/game.project.json'),('portable-quake',folder/'quake.scene.project.json'),('quake-interactive',ROOT/'build/quake-interactive/game.project.json')]:
        original=json.loads(path.read_text());original['name']='test-fixture-'+name;original['scene']=str((path.parent/original['scene']).resolve())
        if original['port']['kind']=='custom':original['port']['sources']=[str((path.parent/p).resolve()) for p in original['port']['sources']]
        project=folder/(name+'.project.json');project.write_text(json.dumps(original,indent=2)+'\n',encoding='utf-8')
        a=argparse.Namespace(project=project,cc='clang',objcopy=None)
        soc.portable_package(a);save(name+'-sdram','test-fixture-'+name+'-sdram');packages.append(name+'-sdram')
    stamp.write_text(json.dumps({'inputs':signature,'packages':packages},indent=2)+'\n',encoding='utf-8')
    return folder
