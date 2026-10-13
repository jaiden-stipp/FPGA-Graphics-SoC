"""Explicit original-engine/SoftFloat experiment; fixed-point builds are unchanged."""
import argparse,concurrent.futures,hashlib,io,json,os,re,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/engine-slice'
LLVM=Path('C:/Program Files/LLVM/bin')
ORIGINAL=['src/game/mario.c','src/game/mario_actions_stationary.c','src/game/mario_actions_moving.c',
          'src/game/mario_actions_airborne.c','src/game/mario_actions_object.c','src/game/mario_step.c','src/engine/math_util.c',
          'src/engine/graph_node.c','src/engine/surface_collision.c']

def run(command):
    r=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(' '.join(map(str,command))+'\n'+r.stdout+r.stderr)
    return r.stdout

def dependency():
    lock=json.loads((ROOT/'softfloat.lock.json').read_text());dest=ROOT/'external/softfloat'
    if not (dest/'SoftFloat-3e/source/softfloat_state.c').exists():
        data=urllib.request.urlopen(lock['url'],timeout=45).read()
        if hashlib.sha256(data).hexdigest()!=lock['archive_sha256']:raise ValueError('SoftFloat archive hash mismatch')
        z=zipfile.ZipFile(io.BytesIO(data))
        for name in z.namelist():
            p=(dest/name).resolve()
            if not p.is_relative_to(dest.resolve()):raise ValueError('Dependency path escapes root')
            if not name.endswith('/'):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    root=dest/'SoftFloat-3e'
    for name,expected in lock.get('files',{}).items():
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('SoftFloat dependency changed: '+name)
    return root

def prepare():
    import sm64_castle
    source=sm64_castle.sm64_subset.fetch();OUT.mkdir(parents=True,exist_ok=True)
    world=sm64_castle.export(OUT/'assets',gameplay=True)
    project=OUT/'assets/game.project.json';spec=json.loads(project.read_text());spec['name']='mario-original-engine-grounds'
    spec['port']['sources']=[s.replace('/castle_game.c','/castle_engine.c') for s in spec['port']['sources']]
    spec['port']['exports']+=['sm64_engine_init','sm64_engine_update','sm64_engine_probe'];project.write_text(json.dumps(spec,indent=2)+'\n')
    world['implementation_status']='Original Mario grounds action/collision slice; full engine, objects and original camera incomplete'
    (OUT/'assets/world.json').write_text(json.dumps(world,indent=2)+'\n')
    a=world['areas'][0];c=a['collision'];v=c['vertices'];tris=c['triangles']
    def shifted(x):return max(0,((x+8192+32768)&65535)-32768)
    def low(x):q=shifted(x);return max(0,q//1024-(q%1024<50))
    def high(x):q=shifted(x);return min(15,q//1024+(q%1024>974))
    nodes=sum(max(0,high(max(v[t[i]][0] for i in range(3)))-low(min(v[t[i]][0] for i in range(3)))+1)*max(0,high(max(v[t[i]][2] for i in range(3)))-low(min(v[t[i]][2] for i in range(3)))+1) for t in tris)
    lines=['#include "surface_terrains.h"','#define ENGINE_SURFACES '+str(len(tris)),'#define ENGINE_NODES '+str(nodes),
           'static const __attribute__((section(".game_assets"))) s16 engine_vertices[][3]={'+','.join('{'+','.join(map(str,p))+'}' for p in v)+'};',
           'static const __attribute__((section(".game_assets"))) s16 engine_triangles[][5]={'+','.join('{'+','.join(map(str,t[:3]))+','+t[3]+','+str(c['triangle_forces'][i])+'}' for i,t in enumerate(tris))+'};',
           'static const __attribute__((section(".game_assets"))) s16 engine_environment[]={'+','.join(map(str,[len(c['water_boxes'])]+[n for box in c['water_boxes'] for n in box]))+'};']
    (OUT/'terrain.inc').write_text('\n'.join(lines)+'\n')
    # Original animation tables/data, with declarations moved ahead of use only.
    # No animation values or frame counts are replaced by proxy timing.
    anim=['#pragma clang section rodata=".game_assets"'];names=[]
    for path in sorted((source/'assets/anims').glob('anim_*.inc.c')):
        text=path.read_text();names.extend(re.findall(r'static const struct Animation\s+(\w+)\[\]',text))
        for typ,sym,body in re.findall(r'static const (u16|s16)\s+(\w+)\[\]\s*=\s*\{(.*?)\};',text,re.S):
            count=len(re.findall(r'-?(?:0x[0-9A-Fa-f]+|\d+)',body))
            anim.append(f'static const {typ} {sym}[{count}];')
        anim.append('#include "'+path.relative_to(source).as_posix()+'"')
    names.sort(key=lambda name:int(name.removeprefix('anim_'),16))
    if [int(name.removeprefix('anim_'),16) for name in names]!=list(range(len(names))):raise ValueError('Original animation IDs are not contiguous')
    anim+=['static const struct Animation *const engine_animations[]={'+','.join(n for n in names)+'};','#pragma clang section rodata=""']
    (OUT/'animations.inc').write_text('\n'.join(anim)+'\n')
    adapter=(ROOT/'firmware/engine/engine_adapter.c').read_text()
    called=set(re.findall(r'return (act_\w+)\(m\)',adapter))|{'mario_reset_bodystate','update_mario_inputs'}
    declarations=[]
    for name in sorted(called):
        match=next((m for rel in ORIGINAL for m in [re.search(r'^((?:s32|u32|void|s16)\s+'+name+r'\([^)]*\))\s*\{',(source/rel).read_text(),re.M)] if m),None)
        if not match:raise ValueError('Missing original engine entry '+name)
        declarations.append(match[1]+';')
    (OUT/'actions.inc').write_text('\n'.join(declarations)+'\n')
    report={'source_commit':json.loads((ROOT/'sm64.lock.json').read_text())['commit'],'original_files':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ORIGINAL+['src/engine/surface_load.c']},'terrain_faces':len(tris),'derived_surface_nodes':nodes,'animation_tables':len(names),'scope':'Original grounds action/collision experiment; no original objects, audio, Lakitu camera, full action dispatch, or save engine'}
    (OUT/'source-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return source

def flags(native=False):
    result=['-O1','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections',
            '-DVERSION_US','-DTARGET_PC','-DAVOID_UB','-DNON_MATCHING',
            '-I'+str(ROOT/'firmware/engine/include'),'-I'+str(ROOT/'external/sm64/include'),
            '-I'+str(ROOT/'external/sm64/src'),'-I'+str(ROOT/'external/sm64'),'-I'+str(OUT),
            '-I'+str(ROOT/'external/sm64/src/game'),'-I'+str(ROOT/'external/sm64/src/engine'),
            '-I'+str(ROOT/'firmware/engine')]
    if native:result+=['-flto','-ffp-contract=off']
    else:result=['--target=riscv32-unknown-elf','-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax']+result
    return result

def native_sources(source):
    # COFF resolves unused-object references before GC. Retain the source call
    # closure instead of supplying fake implementations for unrelated actions.
    paths=ORIGINAL+['src/engine/surface_load.c'];functions={};texts={}
    for relative in paths:
        text=(source/relative).read_text();texts[relative]=text
        clean=re.sub(r'/\*.*?\*/|//[^\n]*',lambda m:' '*len(m[0]),text,flags=re.S)
        pattern=r'^[ \t]*(?:(?:static|inline|UNUSED)\s+)*(?:BAD_RETURN\(\w+\)|(?:struct|union)\s+\w+|\w+)(?:\s+|\s*\*\s*)(\w+)\s*\([^;{}]*?\)\s*\{'
        for match in re.finditer(pattern,clean,re.M):
            if match[1] in {'if','while','for','switch'}:continue
            depth=1;end=match.end()
            while depth and end<len(clean):depth+=(clean[end]=='{')-(clean[end]=='}');end+=1
            if depth:raise ValueError('Cannot parse original function '+match[1])
            if match[1] in functions:raise ValueError('Ambiguous engine function '+match[1])
            functions[match[1]]=(relative,match.start(),end,clean[match.start():end])
    roots='\n'.join((ROOT/'firmware/engine'/p).read_text() for p in ('engine_adapter.c','surface_adapter.c'))
    keep=set(re.findall(r'\b(\w+)\s*\(',roots))&functions.keys()
    while True:
        # Function addresses passed as callbacks (landing/jump handlers) count
        # as dependencies too, even without a following parenthesis.
        called=set(n for name in keep for n in re.findall(r'\b(\w+)\b',functions[name][3]))&functions.keys()
        if called<=keep:break
        keep|=called
    dest=OUT/'native-source'
    for relative,text in texts.items():
        edits=sorted((start,end) for name,(rel,start,end,_) in functions.items() if rel==relative and name not in keep)
        for start,end in reversed(edits):text=text[:start]+'\n'+text[end:]
        p=dest/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    (OUT/'native-source-closure.json').write_text(json.dumps({name:{'file':functions[name][0],'body_sha256':hashlib.sha256(texts[functions[name][0]][functions[name][1]:functions[name][2]].encode()).hexdigest()} for name in sorted(keep)},indent=2)+'\n')
    return dest

def compile_objects(native=False):
    source=prepare();soft=dependency();dest=OUT/('native' if native else 'rv32');dest.mkdir(exist_ok=True)
    overlay=native_sources(source) if native else source
    sf_flags=['-DSOFTFLOAT_FAST_INT64','-DINLINE_LEVEL=0','-DSOFTFLOAT_ROUND_ODD','-I'+str(soft/'source/include'),'-I'+str(soft/'source/8086-SSE')]
    make=(soft/'build/Linux-x86_64-GCC/Makefile').read_text()
    official=set(re.findall(r'\b(\w+)\$\(OBJ\)',make))
    available={p.stem:p for p in list((soft/'source').glob('*.c'))+list((soft/'source/8086-SSE').glob('*.c'))}
    soft_sources=[available[name] for name in sorted(official)]
    # Compile once per source/configuration. Archive GC removes unreferenced formats.
    sources=[overlay/p for p in ORIGINAL]+[ROOT/'firmware/engine'/name for name in ('surface_adapter.c','engine_adapter.c','platform_effects.c','softfloat_abi.c','integer_abi.c')]+soft_sources
    objects=[]
    dependencies=sorted(set(list((ROOT/'firmware/engine').rglob('*.h'))+list((source/'include').rglob('*.h'))+list((source/'src').rglob('*.h'))+list(OUT.glob('*.inc'))+[source/p for p in ORIGINAL]+[source/'src/engine/surface_load.c']))
    dependency_hash=hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in dependencies)).digest()
    def compile_one(pair):
        i,p=pair;obj=dest/(str(i)+'-'+p.stem+'.o');extra=sf_flags if p in soft_sources or p.name=='softfloat_abi.c' else []
        cmd=[LLVM/'clang.exe',*(['-I'+str(overlay)] if native else []),*flags(native),*extra,'-c',p,'-o',obj]
        identity=hashlib.sha256(p.read_bytes()+dependency_hash+json.dumps(list(map(str,cmd))).encode()).hexdigest()
        stamp=obj.with_suffix('.hash')
        if not obj.exists() or not stamp.exists() or stamp.read_text()!=identity:
            run(cmd);stamp.write_text(identity)
        return obj
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(compile_one,pair) for pair in enumerate(sources)]
        for future in futures:
            try:objects.append(future.result())
            except Exception as e:errors.append(str(e))
    if errors:raise RuntimeError('\n'.join(errors))
    archive=dest/'engine.a'
    if archive.exists():archive.unlink()
    run([LLVM/'llvm-ar.exe','rcs',archive,*objects]);print('Compiled original engine and SoftFloat:',len(objects),'objects',flush=True)
    return archive

def diagnostic(native=False):
    archive=compile_objects(native)
    if native:
        names=['sm64_engine_init','sm64_engine_update','sm64_engine_probe','__addsf3','__subsf3','__mulsf3','__divsf3','sqrtf','__muldi3','__ashldi3','__lshrdi3','__ashrdi3','__udivsi3','__divsi3']
        run([LLVM/'clang.exe',*flags(True),'-shared','-fuse-ld=lld','-nostdlib','-Wl,/noentry','-Wl,/opt:ref','-Wl,/include:_fltused',*['-Wl,/export:'+n for n in names],archive,ROOT/'firmware/src/game_memory.c','-o',OUT/'engine.dll'])
    else:
        stem='sm64-original-engine-diagnostic'
        run([LLVM/'clang.exe',*flags(),'-fuse-ld=lld','-nostdlib','-DSOC_SDRAM_EXEC','-DSOC_STACK_CANARY','-Wl,--gc-sections','-Wl,--no-relax','-Wl,--error-limit=0',
             '-I'+str(ROOT/'firmware/include'),'-Wl,-T,firmware/link-sdram-exec.ld','-Wl,-Map,build/'+stem+'.map',
             ROOT/'firmware/start.S',ROOT/'firmware/engine/diagnostic.c',ROOT/'firmware/src/game_memory.c',archive,'-o',ROOT/'build'/ (stem+'.elf')])
        from sdram_execution import extract
        segments,execution=extract(ROOT,stem,str(LLVM/'llvm-objcopy.exe'),str(LLVM/'llvm-nm.exe'))
        package={'format':'soc-game-package','version':1,'app':'original-engine-diagnostic','segments':segments,'execution':execution,'required_cpu_features':{'sdram-exec-v1':True,'mul':True}}
        (ROOT/'build'/(stem+'.package.json')).write_text(json.dumps(package,indent=2)+'\n')
        print('Linked diagnostic:',[(s['file'],s['bytes']) for s in segments],execution,flush=True)

def audit_isa(elf):
    text=run([LLVM/'llvm-objdump.exe','-d',elf]);instructions=[];muls=[]
    allowed={0x03,0x23,0x13,0x33,0x37,0x17,0x63,0x6f,0x67}
    for address,encoded in re.findall(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s',text,re.M):
        word=int(encoded,16);op=word&127
        if op not in allowed:raise ValueError('Unsupported executable opcode at '+address+': '+encoded)
        if op==0x33 and word>>25==1:
            if (word>>12)&7:raise ValueError('Only low MUL is implemented: '+address)
            muls.append(int(address,16))
        instructions.append(int(address,16))
    if not instructions or not muls:raise ValueError('Missing decoded instructions or required MUL helper')
    undefined=run([LLVM/'llvm-nm.exe','--undefined-only',elf]).strip()
    if undefined:raise ValueError('Unresolved runtime symbols: '+undefined)
    report={'compiler_isa':'rv32i','extra_instruction':'low MUL only','decoded_instruction_count':len(instructions),'mul_addresses':muls,'unresolved_symbols':[]}
    elf.with_suffix('.isa.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def game():
    from portable_game import generate
    from rv32i_subset import check
    from sdram_execution import extract
    archive=compile_objects(False)
    project=OUT/'assets/game.project.json';spec=json.loads(project.read_text());spec['name']='mario-original-engine-grounds'
    spec['port']['sources']=[s.replace('/castle_game.c','/castle_engine.c') for s in spec['port']['sources']]
    for name in ['sm64_engine_init','sm64_engine_update','sm64_engine_probe']:
        if name not in spec['port']['exports']:spec['port']['exports'].append(name)
    project.write_text(json.dumps(spec,indent=2)+'\n')
    spec,content,target,sources,api,_=generate(project)
    api=set(api)|{'portable_assets','portable_world','portable_camera','portable_meshes'}
    common=[ROOT/'firmware/src'/name for name in ('gfx.c','gfx_scene.c','player.c','first_person.c','game_runtime.c','portable_assets.c','portable_main.c','cpu_profile.c','sdram.c')]
    options=['-DGAME_USE_SDRAM','-DSOC_SDRAM_EXEC','-DSOC_STACK_CANARY','-DSOC_INTEGER_MUL','-DSOC_GEOMETRY_OFFLOAD','-DGFX_PACKED','-DWORLD_FORCE_DIRECT=1','-DGAME_UNCAPPED_RENDER','-DGAME_RENDER_INTERPOLATION']
    cpp=['-I'+str(ROOT/'firmware/include'),'-I'+str(ROOT/'firmware/generated')]
    objects=[]
    for i,source in enumerate(common+sources):
        check(source,str(LLVM/'clang.exe'),additional_api=api,extra_flags=options)
        obj=OUT/'rv32'/('renderer-'+str(i)+'.o');run([LLVM/'clang.exe',*cpp,*flags(),*options,'-Wall','-Wextra','-Werror','-c',source,'-o',obj]);objects.append(obj)
    stem='mario-original-engine-grounds-exec'
    run([LLVM/'clang.exe',*flags(),*cpp,*options,'-fuse-ld=lld','-nostdlib','-Wl,--gc-sections','-Wl,--no-relax','-Wl,-T,firmware/link-sdram-exec.ld','-Wl,-Map,build/'+stem+'.map',ROOT/'firmware/start.S',*objects,archive,'-o',ROOT/'build'/(stem+'.elf')])
    segments,execution=extract(ROOT,stem,str(LLVM/'llvm-objcopy.exe'),str(LLVM/'llvm-nm.exe'));audit_isa(ROOT/'build'/(stem+'.elf'))
    package={'format':'soc-game-package','version':1,'app':'original-engine-grounds','segments':segments,'execution':execution,'required_cpu_features':{'sdram-exec-v1':True,'mul':True,'geometry-worker-v1':True},'target':target,'content':content,'cadence':{'simulation_tick_cycles':1666667,'clock_hz':50000000,'render':'uncapped','render_repeat_safe':True,'interpolation':True}}
    path=ROOT/'build'/(stem+'.package.json');path.write_text(json.dumps(package,indent=2)+'\n')
    from load_game import package_segments
    package_segments(path);print('Built original-engine grounds:',path,[(s['file'],s['bytes']) for s in segments],flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','objects','diagnostic','game']);p.add_argument('--native',action='store_true');a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='objects':compile_objects(a.native)
    elif a.action=='game':game()
    else:
        diagnostic(a.native)
        if not a.native:audit_isa(ROOT/'build/sm64-original-engine-diagnostic.elf')
if __name__=='__main__':main()
