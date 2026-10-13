"""Isolated real-CPU/real-controller simulation; never programs the FPGA."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/sdram-execution'
LLVM=Path('C:/Program Files/LLVM/bin')
MS=Path('C:/intelFPGA/18.1/modelsim_ase/win32aloem')
NAMES=['uncached-fetch','unified-4k','split-blocking-4k-4k','split-fast-4k-4k','local-reference','local-overlays','unified-8k']
WORKLOADS=['hot-routine','alternating-conflicts','large-streaming']

def run(argv,log=None):
    p=subprocess.run([str(x) for x in argv],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if log:log.write_text(p.stdout,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stdout)
    return p.stdout

def fixture(case,mode):
    stem=OUT/f'case{case}-mode{mode}'
    # Every architecture executes the same arithmetic and external data accesses.
    # Local-reference links both routines locally; overlays copy into one slot.
    a=0x2000 if mode==4 else 0x80000000
    b=0x8000 if mode==4 else (0x80020000 if case==2 else 0x80001000)
    calls=16 if case==0 else (32 if case==1 else 4)
    def routine(which):
        if case==2:
            return '\n'.join([f'addi a0,a0,{which+1}']*2048+['ret'])+'\n'
        offset=which*4;inc=which+1;op='xor' if which else 'add'
        return f'''li t2,16
1: lw t0,{offset}(s0)
addi t0,t0,{inc}
sw t0,{offset}(s0)
{op} a0,a0,t0
mul a0,a0,s3
addi t2,t2,-1
bnez t2,1b
ret
'''
    ra,rb=routine(0),routine(1)
    count=2049 if case==2 else 9
    main=['.option norvc','.option norelax','.section .text.boot,"ax"','.global _start',
          '_start:','li s0,0x80040000','li s3,3','li a0,0']
    last=None;overlays=0;copied=0;expected=0;state=[0,0]
    for n in range(calls):
        which=0 if case==0 else n%2
        source=a if which==0 else b
        if mode==5 and which!=last:
            main += [f'li t3,{source}','li t4,0x2000',f'li t5,{count}',f'copy{n}:',
                     'lw t1,0(t3)','sw t1,0(t4)','addi t3,t3,4','addi t4,t4,4',
                     'addi t5,t5,-1',f'bnez t5,copy{n}']
            overlays+=1;copied+=count*4;last=which
        target=0x2000 if mode==5 else source
        main += [f'li t3,{target}','jalr ra,0(t3)']
        if case==2:expected=(expected+2048*(which+1))&0xffffffff
        else:
            for _ in range(16):
                state[which]+=which+1
                expected=((expected^state[which]) if which else (expected+state[which]))*3&0xffffffff
    main += ['mv t6,a0','1: j 1b','.section .module_a,"ax"',ra,'.section .module_b,"ax"',rb]
    stem.with_suffix('.S').write_text('\n'.join(main)+'\n',encoding='utf-8')
    linker=f'''OUTPUT_ARCH(riscv)
ENTRY(_start)
PHDRS {{ boot PT_LOAD; a PT_LOAD; b PT_LOAD; }}
SECTIONS {{ .text 0 : {{ *(.text.boot) }} :boot .module_a 0x{a:x} : {{ *(.module_a) }} :a .module_b 0x{b:x} : {{ *(.module_b) }} :b }}
'''
    stem.with_suffix('.ld').write_text(linker,encoding='utf-8')
    run([LLVM/'clang.exe','--target=riscv32','-march=rv32im','-mabi=ilp32','-nostdlib','-fuse-ld=lld',
         '-Wl,--no-relax',f'-Wl,-T,{stem.with_suffix(".ld")}',stem.with_suffix('.S'),'-o',stem.with_suffix('.elf')],stem.with_suffix('.compile.log'))
    if stem.with_suffix('.elf').stat().st_size>1024*1024:
        raise RuntimeError('Diagnostic ELF unexpectedly exceeds 1 MiB; check segment layout')
    dis=run([LLVM/'llvm-objdump.exe','-d',stem.with_suffix('.elf')],stem.with_suffix('.disassembly.txt'))
    # Extract only the three declared sections; no giant sparse flat ELF image.
    local=[0x13]*16384;external={0x10000:0,0x10001:0};sizes={}
    for name,address in [('text',0),('module_a',a),('module_b',b)]:
        target=stem.with_name(stem.name+'.'+name+'.bin')
        run([LLVM/'llvm-objcopy.exe','--only-section=.'+name,'-O','binary',stem.with_suffix('.elf'),target])
        data=target.read_bytes();sizes[name]=len(data)
        assert len(data)%4==0
        if name.startswith('module'):assert len(data)==count*4,(name,len(data),count)
        for offset in range(0,len(data),4):
            word=int.from_bytes(data[offset:offset+4],'little');where=address+offset
            if where<65536:local[where//4]=word
            else:external[(where-0x80000000)//4]=word
    stem.with_name(stem.name+'.local.hex').write_text(''.join(f'{w:08x}\n' for w in local),encoding='utf-8')
    stem.with_name(stem.name+'.external.txt').write_text(f'{expected:08x}\n'+''.join(f'{k:07x} {v:08x}\n' for k,v in sorted(external.items())),encoding='utf-8')
    return {'expected_result':expected,'section_bytes':sizes,'overlay_loads':overlays,'overlay_copied_bytes':copied,
            'source_module_b_address':b,'calls':calls}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--smoke',action='store_true');args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=run(['git','rev-parse','HEAD']).strip()
    from soc import sources
    production=sources(False)+[ROOT/'sim/sdram_device_model.sv']
    protected=set(production)|set((ROOT/'rtl').rglob('*.sv'))|set((ROOT/'rtl').rglob('*.v'))|set((ROOT/'fpga').rglob('*.sdc'))
    protected.add(ROOT/'profiles/current-deployment.json')
    selected=json.loads((ROOT/'profiles/current-deployment.json').read_text(encoding='utf-8'))
    protected.add(ROOT/selected['hardware']['file'])
    fingerprints={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(protected)}
    (OUT/'baseline.json').write_text(json.dumps({'commit':baseline,'inputs':fingerprints},indent=2)+'\n',encoding='utf-8')
    lib=OUT/'simlib'
    if not lib.exists():run([MS/'vlib.exe',lib])
    experiment=list((ROOT/'experiments/sdram-execution').glob('*.sv'))
    # Derive a capacity-parameterized copy for the equal-capacity comparison.
    # The production cache source and generator remain unchanged.
    cache=(ROOT/'rtl/sdram_cache.sv').read_text(encoding='utf-8')
    substitutions={
        'module sdram_cache #(parameter ENABLE_BURST = 1, parameter CACHE_LINE_BYTES = 32)':
        'module execution_data_cache #(parameter ENABLE_BURST = 1, parameter CACHE_LINE_BYTES = 32, parameter CACHE_BYTES=4096)',
        'localparam LINE_WORDS = CACHE_LINE_BYTES / 4;':
        'localparam WORD_COUNT=CACHE_BYTES/4; localparam WORD_BITS=$clog2(WORD_COUNT);\n    localparam LINE_WORDS = CACHE_LINE_BYTES / 4;',
        '1024 / LINE_WORDS':'WORD_COUNT / LINE_WORDS','[0:1023]':'[0:WORD_COUNT-1]',
        '[14:0]':'[24-WORD_BITS:0]','[9-OFFSET_BITS:0]':'[WORD_BITS-1-OFFSET_BITS:0]',
        '[9:OFFSET_BITS]':'[WORD_BITS-1:OFFSET_BITS]','[24:10]':'[24:WORD_BITS]',
        '[9:0]':'[WORD_BITS-1:0]'}
    for before,after in substitutions.items():
        assert before in cache,before
        cache=cache.replace(before,after)
    generated=OUT/'parameterized_cache.sv';generated.write_text(cache,encoding='utf-8');experiment.append(generated)
    run([MS/'vlog.exe','-work',lib,'-sv','-mfcu','+incdir+'+str(ROOT/'external/renderer/rtl/common'),'+define+SOC_DISABLE_COMMAND_DMA']+production+experiment,OUT/'compile.log')
    output=run([MS/'vsim.exe','-c','-lib',lib,'fetch_cache_tb','-do','onerror {quit -code 1}; run -all; quit -code 0'],OUT/'fetch-cache.simulation.log')
    if 'PASS fetch_cache_tb' not in output or '** Error:' in output or '** Fatal:' in output:raise RuntimeError(output)
    rows=[]
    for case in range(1 if args.smoke else 3):
        for mode in range(7):
            spec=fixture(case,mode)
            log=OUT/f'case{case}-mode{mode}.simulation.log'
            output=run([MS/'vsim.exe','-c','-lib',lib,'execution_tb',f'-gMODE={mode}',f'-gCASE_ID={case}',
                '-do','onerror {quit -code 1}; run -all; quit -code 0'],log)
            if 'PASS execution_tb' not in output or '** Error:' in output or '** Fatal:' in output:raise RuntimeError(output)
            match=re.search(r'RESULT (.*)',output)
            counts={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',match[1])}
            trace=OUT/f'case{case}-mode{mode}.retirement.txt'
            row={'architecture':NAMES[mode],'workload':WORKLOADS[case],**spec,**counts,
                 'retirement_trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest()}
            rows.append(row)
            (OUT/'results.json').write_text(json.dumps({'scope':'RTL simulation with real pipeline/controller and synthetic workload; not board or SM64 performance','baseline_commit':baseline,'rows':rows},indent=2)+'\n',encoding='utf-8')
            print(NAMES[mode],WORKLOADS[case],counts['cycles'],'cycles',flush=True)
        direct=[x for x in rows if x['case']==case and x['mode'] in (0,1,2,3,6)]
        assert len({(x['retired'],x['trace_hash']) for x in direct})==1,'Architectures retired different execution traces'
        assert len({x['retirement_trace_sha256'] for x in direct})==1,'Full retirement traces differ'
    for name,digest in fingerprints.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    print('All original RTL inputs unchanged. No FPGA programming performed.',flush=True)
if __name__=='__main__':main()
