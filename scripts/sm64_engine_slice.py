"""Explicit original-engine/SoftFloat experiment; fixed-point builds are unchanged."""
import argparse,concurrent.futures,hashlib,io,json,os,re,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/engine-slice'
LLVM=Path('C:/Program Files/LLVM/bin')
def llvm_tool(name):
    found=shutil.which(name)
    if found:return Path(found)
    fallback=LLVM/(name+'.exe')
    if os.name=='nt' and fallback.is_file():return fallback
    raise FileNotFoundError('Install LLVM and add '+name+' to PATH')

def native_library():
    return OUT/('engine.dll' if os.name=='nt' else 'engine.so')
FLOAT_VERTICES=False
ORIGINAL=['src/game/mario.c','src/game/mario_actions_stationary.c','src/game/mario_actions_moving.c',
          'src/game/mario_actions_airborne.c','src/game/mario_actions_object.c','src/game/mario_step.c','src/engine/math_util.c',
          'src/engine/graph_node.c','src/engine/surface_collision.c',
          'src/game/mario_actions_automatic.c','src/game/mario_actions_cutscene.c','src/game/interaction.c',
          'src/game/mario_misc.c','src/engine/behavior_script.c']
INCLUDED=['src/engine/surface_load.c','src/game/mario_actions_submerged.c','src/game/camera.c']+['src/game/behaviors/'+p+'.inc.c' for p in ('intro_peach','intro_lakitu','end_birds_1','end_birds_2','intro_scene')]

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
    spec['port']['exports']+=['sm64_engine_init','sm64_engine_init_heading','sm64_engine_update','sm64_engine_probe','sm64_engine_pose','sm64_engine_camera_step','sm64_engine_visual_probe'];project.write_text(json.dumps(spec,indent=2)+'\n')
    world['implementation_status']='Original grounds actions/collision, engine-selected animation and normal Lakitu camera; fixed mesh switches, cutscenes, objects, other areas and full engine incomplete'
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
    grounds_script=re.sub(r'/\*.*?\*/|//[^\n]*','',(source/'levels/castle_grounds/script.c').read_text(),flags=re.S)
    spawn=re.search(r'MARIO_POS\(\s*1\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)',grounds_script)
    if not spawn or list(map(int,spawn.groups()[1:]))!=a['spawn']:raise ValueError('Original grounds spawn differs from world manifest')
    (OUT/'spawn.inc').write_text('#define ENGINE_GROUNDS_SPAWN_YAW '+str((int(spawn[1])*65536//360)&65535)+'u\n')
    animation=world['animation'];rig=animation['joints'];verts=animation['vertex_sources'];display=animation['display_joints']
    if max(abs(x) for v in verts for x in v['local'])>4096:raise ValueError('Visual Q14 product proof requires raw coordinates <=4096')
    profile=json.loads((ROOT/'profiles/sm64-mario-sdram.json').read_text())
    geo_text=(source/profile['animation']['geo_source']).read_text()
    main_geo=re.search(r'const GeoLayout mario_geo\[\]\s*=\s*\{(.*?)\};',geo_text,re.S)[1]
    scale=re.search(r'GEO_SCALE\([^,]+,\s*(\d+)\)',main_geo)[1]
    head_parts=[p['display_list'] for p in profile['actor']['parts'] if 'cap_on' in p['display_list']]
    if len(head_parts)!=1:raise ValueError('Selected Mario mesh must identify one cap-on head display list')
    head=display[head_parts[0]]
    visual=['#define ENGINE_VISUAL_JOINTS '+str(len(rig)), '#define ENGINE_VISUAL_VERTICES '+str(len(verts)),
            '#define ENGINE_MODEL_SCALE_Q16 '+scale,'#define ENGINE_TORSO_JOINT '+str(display['mario_low_poly_torso']),
            '#define ENGINE_HEAD_JOINT '+str(head),
            'static const __attribute__((section(".game_assets"))) s16 visual_joints[][4]={'+','.join('{'+','.join(map(str,[j['parent'],*j['translation']]))+'}' for j in rig)+'};',
            'static const __attribute__((section(".game_assets"))) s16 visual_vertices[][3]={'+','.join('{'+','.join(map(str,v['local']))+'}' for v in verts)+'};',
            'static const __attribute__((section(".game_assets"))) u8 visual_bindings[]={'+','.join(str(v['joint']) for v in verts)+'};']
    for label,part in [('LEFT_HAND','mario_low_poly_left_hand_closed'),('RIGHT_HAND','mario_low_poly_right_hand_closed'),('RIGHT_FOOT','mario_low_poly_right_foot')]:
        visual.append('#define ENGINE_'+label+'_JOINT '+str(display[part]))
    (OUT/'visual.inc').write_text('\n'.join(visual)+'\n')
    # Copy adapter warp deadlines from the pinned upstream service rather than
    # maintaining unrelated timing literals.
    level_text=(source/'src/game/level_update.c').read_text();delays=[]
    for op in ('DEATH','WARP_FLOOR'):
        match=re.search(r'case WARP_OP_'+op+r':(?:(?!case WARP_OP_).)*?sDelayedWarpTimer\s*=\s*(\d+)',level_text,re.S)
        if not match:raise ValueError('Missing original warp delay '+op)
        delays.append('#define ENGINE_'+op+'_DELAY '+match[1])
    (OUT/'respawn.inc').write_text('\n'.join(delays)+'\n')
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
    called=set(re.findall(r'return (act_\w+)\(m\)',adapter))|{'mario_reset_bodystate','update_mario_inputs',
        'check_common_stationary_cancels','check_common_moving_cancels','check_common_airborne_cancels',
        'check_common_automatic_cancels','play_far_fall_sound','update_mario_health','update_mario_info_for_cam',
        'sink_mario_in_quicksand','squish_mario_model','mario_handle_special_floors'}
    declarations=[]
    for name in sorted(called):
        match=next((m for rel in ORIGINAL for m in [re.search(r'^((?:s32|u32|void|s16)\s+'+name+r'\([^)]*\))\s*\{',(source/rel).read_text(),re.M)] if m),None)
        if not match:raise ValueError('Missing original engine entry '+name)
        declarations.append(match[1]+';')
    (OUT/'actions.inc').write_text('\n'.join(declarations)+'\n')
    report={'source_commit':json.loads((ROOT/'sm64.lock.json').read_text())['commit'],'original_files':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ORIGINAL+INCLUDED},'service_source_files':{p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in ('src/game/level_update.c','levels/castle_grounds/script.c','actors/mario/geo.inc.c','src/game/rendering_graph_node.c')},'terrain_faces':len(tris),'derived_surface_nodes':nodes,'animation_tables':len(names),'visual':{'joints':len(rig),'vertices':len(verts),'model_scale_q16':int(scale),'root_motion':'original flags and all eligible translation channels','callbacks':['geo_mario_tilt_torso','geo_mario_head_rotation','geo_mario_hand_foot_scaler'],'final_vertices':'Q14 matrix lowering; original SDK float reference available for comparison'},'scope':'Original grounds movement and normal Lakitu camera with engine-selected visual animation; fixed eye/cap/hand switches, objects, audio, cutscenes, other areas, full action dispatch and saves incomplete'}
    (OUT/'source-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return source

def flags(native=False):
    result=['-O1','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections',
            '-DVERSION_US','-DTARGET_PC','-DAVOID_UB','-DNON_MATCHING',
            '-I'+str(ROOT/'firmware/engine/include'),'-I'+str(ROOT/'external/sm64/include'),
            '-I'+str(ROOT/'external/sm64/src'),'-I'+str(ROOT/'external/sm64'),'-I'+str(OUT),
            '-I'+str(ROOT/'external/sm64/src/game'),'-I'+str(ROOT/'external/sm64/src/engine'),
            '-I'+str(ROOT/'firmware/engine')]
    if native:
        result+=['-flto','-ffp-contract=off','-DSOC_ENGINE_TEST']
        if os.name!='nt':result+=['-fPIC']
    else:result=['--target=riscv32-unknown-elf','-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax']+result
    return result

def native_sources(source):
    # COFF resolves unused-object references before GC. Retain the source call
    # closure instead of supplying fake implementations for unrelated actions.
    paths=ORIGINAL+[p for p in INCLUDED if '/behaviors/' not in p];functions={};texts={}
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
    roots='\n'.join((ROOT/'firmware/engine'/p).read_text() for p in ('engine_adapter.c','surface_adapter.c','submerged_adapter.c','visual_adapter.c','camera_adapter.c'))
    arrays={}
    camera=texts['src/game/camera.c']
    for match in re.finditer(r'^[ \t]*(?:(?:static|const)\s+)*(?:struct\s+\w+|\w+)(?:\s+|\s*\*\s*)(\w+)\s*(?:\[[^\]]*\]\s*)+\s*=\s*\{',camera,re.M):
        depth=1;end=match.end()
        while depth and end<len(camera):depth+=(camera[end]=='{')-(camera[end]=='}');end+=1
        if depth:raise ValueError('Cannot parse camera table '+match[1])
        arrays[match[1]]=(match.start(),camera.index(';',end)+1,camera[match.start():end])
    roots+='\n'+'\n'.join(re.findall(r'^STATIC_ASSERT.*$',camera,re.M))
    keep=set(re.findall(r'\b(\w+)\s*\(',roots))&functions.keys();tables=set()
    while True:
        # Function addresses passed as callbacks (landing/jump handlers) count
        # as dependencies too, even without a following parenthesis.
        tokens=set(re.findall(r'\b(\w+)\b',roots+'\n'+'\n'.join(functions[name][3] for name in keep)+'\n'+'\n'.join(arrays[name][2] for name in tables)))
        called=tokens&functions.keys();used_tables=tokens&arrays.keys()
        if called<=keep and used_tables<=tables:break
        keep|=called;tables|=used_tables
    dest=OUT/'native-source'
    for relative,text in texts.items():
        edits=sorted((start,end) for name,(rel,start,end,_) in functions.items() if rel==relative and name not in keep)
        if relative=='src/game/camera.c':edits+= [(start,end) for name,(start,end,_) in arrays.items() if name not in tables]
        array_edits={(start,end) for name,(start,end,_) in arrays.items() if name not in tables} if relative=='src/game/camera.c' else set()
        for start,end in sorted(edits,reverse=True):
            declaration='' if (start,end) in array_edits else text[start:text.index('{',start)].rstrip()+';\n'
            text=text[:start]+declaration+text[end:]
        if relative=='src/game/camera.c':
            # The grounds normal-camera closure does not instantiate cinematic
            # actors. Their conditional compilation has alternate brace bodies.
            text=re.sub(r'^#include "behaviors/[^\"]+"\s*$', '',text,flags=re.M)
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
    sources=[overlay/p for p in ORIGINAL]+[ROOT/'firmware/engine'/name for name in ('surface_adapter.c','engine_adapter.c','submerged_adapter.c','visual_adapter.c','camera_adapter.c','platform_effects.c','softfloat_abi.c','integer_abi.c')]+soft_sources
    objects=[]
    dependencies=sorted(set(list((ROOT/'firmware/engine').rglob('*.h'))+list((source/'include').rglob('*.h'))+list((source/'src').rglob('*.h'))+list(OUT.glob('*.inc'))+[source/p for p in ORIGINAL+INCLUDED]))
    dependency_hash=hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in dependencies)).digest()
    def compile_one(pair):
        i,p=pair;obj=dest/(str(i)+'-'+p.stem+'.o');extra=sf_flags if p in soft_sources or p.name=='softfloat_abi.c' else []
        if not native and p.name=='camera_adapter.c':extra+=['-mllvm','-enable-global-merge=false']
        if FLOAT_VERTICES and p.name=='visual_adapter.c':extra+=['-DSOC_VISUAL_FLOAT_REFERENCE']
        cmd=[llvm_tool('clang'),*(['-I'+str(overlay)] if native else []),*flags(native),*extra,'-c',p,'-o',obj]
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
    run([llvm_tool('llvm-ar'),'rcs',archive,*objects]);print('Compiled original engine and SoftFloat:',len(objects),'objects',flush=True)
    return archive

def diagnostic(native=False,visual=False):
    archive=compile_objects(native)
    if native:
        names=['sm64_engine_init','sm64_engine_init_heading','sm64_engine_update','sm64_engine_probe','sm64_engine_pose','sm64_engine_camera_step','sm64_engine_visual_probe','sm64_engine_test_animation','sm64_engine_test_float_pose','sm64_engine_test_place','__addsf3','__subsf3','__mulsf3','__divsf3','sqrtf','__muldi3','__ashldi3','__lshrdi3','__ashrdi3','__udivsi3','__divsi3']
        if os.name=='nt':
            link=['-Wl,/noentry','-Wl,/opt:ref','-Wl,/include:_fltused',*['-Wl,/export:'+n for n in names]]
        else:
            link=['-Wl,--gc-sections','-Wl,--no-undefined',*['-Wl,-u,'+n for n in names]]
        run([llvm_tool('clang'),*flags(True),'-shared','-fuse-ld=lld','-nostdlib',*link,archive,ROOT/'firmware/src/game_memory.c','-o',native_library()])
    else:
        stem=('sm64-original-visual-float-diagnostic' if FLOAT_VERTICES else 'sm64-original-visual-diagnostic') if visual else 'sm64-original-engine-diagnostic'
        run([llvm_tool('clang'),*flags(),'-fuse-ld=lld','-nostdlib','-DSOC_SDRAM_EXEC','-DSOC_STACK_CANARY','-Wl,--gc-sections','-Wl,--no-relax','-Wl,--error-limit=0',
             '-I'+str(ROOT/'firmware/include'),'-Wl,-T,firmware/link-sdram-exec.ld','-Wl,-Map,build/'+stem+'.map',
             ROOT/'firmware/start.S',ROOT/'firmware/engine'/('visual_diagnostic.c' if visual else 'diagnostic.c'),ROOT/'firmware/src/game_memory.c',archive,'-o',ROOT/'build'/ (stem+'.elf')])
        from sdram_execution import extract
        segments,execution=extract(ROOT,stem,str(llvm_tool('llvm-objcopy')),str(llvm_tool('llvm-nm')))
        package={'format':'soc-game-package','version':1,'app':'original-engine-diagnostic','segments':segments,'execution':execution,'required_cpu_features':{'sdram-exec-v1':True,'mul':True}}
        (ROOT/'build'/(stem+'.package.json')).write_text(json.dumps(package,indent=2)+'\n')
        print('Linked diagnostic:',[(s['file'],s['bytes']) for s in segments],execution,flush=True)

def audit_isa(elf):
    from rv32i_subset import instruction_words
    text=run([llvm_tool('llvm-objdump'),'-d',elf]);instructions=[];muls=[]
    allowed={0x03,0x23,0x13,0x33,0x37,0x17,0x63,0x6f,0x67}
    for location,word in instruction_words(text):
        address=f'{location:x}';encoded=f'{word:08x}';op=word&127
        if op not in allowed:raise ValueError('Unsupported executable opcode at '+address+': '+encoded)
        if op==0x33 and word>>25==1:
            if (word>>12)&7:raise ValueError('Only low MUL is implemented: '+address)
            muls.append(int(address,16))
        instructions.append(int(address,16))
    if not instructions or not muls:raise ValueError('Missing decoded instructions or required MUL helper')
    undefined=run([llvm_tool('llvm-nm'),'--undefined-only',elf]).strip()
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
        check(source,str(llvm_tool('clang')),additional_api=api,extra_flags=options+['-I'+str(OUT)])
        obj=OUT/'rv32'/('renderer-'+str(i)+'.o');run([llvm_tool('clang'),*cpp,*flags(),*options,'-Wall','-Wextra','-Werror','-c',source,'-o',obj]);objects.append(obj)
    stem='mario-original-engine-grounds-exec'
    run([llvm_tool('clang'),*flags(),*cpp,*options,'-fuse-ld=lld','-nostdlib','-Wl,--gc-sections','-Wl,--no-relax','-Wl,-T,firmware/link-sdram-exec.ld','-Wl,-Map,build/'+stem+'.map',ROOT/'firmware/start.S',*objects,archive,'-o',ROOT/'build'/(stem+'.elf')])
    segments,execution=extract(ROOT,stem,str(llvm_tool('llvm-objcopy')),str(llvm_tool('llvm-nm')));audit_isa(ROOT/'build'/(stem+'.elf'))
    package={'format':'soc-game-package','version':1,'app':'original-engine-grounds','segments':segments,'execution':execution,'required_cpu_features':{'sdram-exec-v1':True,'mul':True,'geometry-worker-v1':True},'target':target,'content':content,'cadence':{'simulation_tick_cycles':1666667,'clock_hz':50000000,'render':'uncapped','render_repeat_safe':True,'interpolation':True}}
    path=ROOT/'build'/(stem+'.package.json');path.write_text(json.dumps(package,indent=2)+'\n')
    from load_game import package_segments
    package_segments(path);print('Built original-engine grounds:',path,[(s['file'],s['bytes']) for s in segments],flush=True)

def main():
    global FLOAT_VERTICES
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','objects','diagnostic','game']);p.add_argument('--native',action='store_true');p.add_argument('--visual',action='store_true');p.add_argument('--float-vertices',action='store_true',help='Original SDK float vertex reference diagnostic');a=p.parse_args()
    if a.float_vertices and (a.action!='diagnostic' or not a.visual or a.native):p.error('--float-vertices requires diagnostic --visual without --native')
    FLOAT_VERTICES=a.float_vertices
    if a.action=='prepare':prepare()
    elif a.action=='objects':compile_objects(a.native)
    elif a.action=='game':game()
    else:
        diagnostic(a.native,a.visual)
        if not a.native:audit_isa(ROOT/'build'/((('sm64-original-visual-float-diagnostic.elf' if FLOAT_VERTICES else 'sm64-original-visual-diagnostic.elf') if a.visual else 'sm64-original-engine-diagnostic.elf')))
if __name__=='__main__':main()
