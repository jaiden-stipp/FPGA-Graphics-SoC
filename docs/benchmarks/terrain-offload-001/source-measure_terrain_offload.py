"""Reproduce controlled terrain/fine-profile comparisons; always restore normal Mario."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import soc
from profile_cpu import collect
from rv32i_subset import check

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/terrain-offload'
CASES=[('before','mario-castle-fixed-pose-mul',False),
       ('direct','terrain-fixed-direct-mul',False),
       ('safe','terrain-fixed-safe-mul',False),
       ('fine-direct','terrain-fixed-direct-fine-mul',False),
       ('fine-safe','terrain-fixed-safe-fine-mul',False),
       ('fine-safe-moving','terrain-fixed-safe-fine-mul',True)]

def build(project):
    spec=json.loads(project.read_text());base=json.loads((ROOT/'build/mario-castle-sdram-direct-mul.package.json').read_text())
    sources=[(project.parent/p).resolve() for p in spec['port']['sources']]
    api=set(spec['port']['exports'])|{'portable_meshes'}
    for direct,fine in ((True,False),(False,False),(True,True),(False,True)):
        flags=['-DSOC_PROFILE','-DSOC_PROFILE_DETAIL','-DSOC_INTEGER_MUL','-DCASTLE_PROFILE_FIXED_POSE']
        if direct:flags+=['-DWORLD_FORCE_DIRECT=1']
        if fine:flags+=['-DSOC_PROFILE_FINE']
        for source in [*sources,ROOT/'firmware/src/gfx.c',ROOT/'firmware/src/cpu_profile.c']:
            check(source,'clang',additional_api=api,extra_flags=flags)
        stem='terrain-fixed-'+('direct' if direct else 'safe')+('-fine' if fine else '')+'-mul'
        args=SimpleNamespace(cc='clang',objcopy=None,app='portable',boot=None,use_sdram=True,image_name=stem,extra_flags=flags,port_sources=sources,content=base['content'],target=base['target'])
        soc.firmware(args)

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    restore=ROOT/'build/mario-castle-sdram-direct-mul.package.json'
    old=ROOT/'build/mario-castle-fixed-pose-mul.bin'
    if hashlib.sha256(old.read_bytes()).hexdigest()!='fc09b6f8e5424f83343567bcbc3504a027fb3f4f8d1af3b096b8dd2035df5170':
        raise ValueError('Preserved pre-change fixed-pose baseline differs; do not substitute an unlabelled rebuild')
    manifest={'baseline_revision':'6b8a298','candidate_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'cases':[],'artifacts':[]}
    # Preserve exact CPU/assets/package bytes locally before comparisons.
    for _,stem,_ in CASES:
        for suffix in ('.bin','.assets.bin','.package.json','.symbols.json'):
            path=ROOT/'build'/(stem+suffix)
            manifest['artifacts'].append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    try:
        for label,stem,moving in CASES:
            print('BEGIN',label,flush=True)
            collect(ROOT/'build'/(stem+'.package.json'),ROOT/'build'/(stem+'.symbols.json'),restore,OUT/(label+'.json'),trials=3,moving=moving,reuse_immutable_assets=True)
            manifest['cases'].append(label)
    finally:
        (OUT/'experiment.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--project',type=Path,default=ROOT/'build/castle/game.project.json');a=p.parse_args()
    if not a.build and not a.run:p.error('Choose --build and/or --run')
    if a.build:build(a.project)
    if a.run:run()
