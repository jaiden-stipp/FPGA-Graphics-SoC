"""Build a diagnostic or isolated timing-gated SDRAM-execution hardware image."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
import soc
from sdram_execution import extract
from measure_pixel_lanes import timing_gate
ROOT=soc.ROOT;OUT=ROOT/'build/sdram-exec';LLVM=Path('C:/Program Files/LLVM/bin')
NAME='SdramExecSoC';FIT=ROOT/'build/quartus-sdram-exec'

def firmware():
    OUT.mkdir(parents=True,exist_ok=True);stem='sdram-exec-test'
    from rv32i_subset import check
    check(ROOT/'firmware/src/sdram_exec_test.c',str(LLVM/'clang.exe'),additional_api={'far_step','diagnostic_record','initialized_value','zero_value','local_zero','local_initialized'})
    cmd=[str(LLVM/'clang.exe'),'--target=riscv32','-fuse-ld=lld','-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax',
         '-O1','-ffreestanding','-fno-builtin','-nostdlib','-ffunction-sections','-fdata-sections','-Wall','-Wextra','-Werror',
         '-DSOC_SDRAM_EXEC','-Ifirmware/include','-Wl,-T,firmware/link-sdram-exec.ld','-Wl,--no-relax',f'-Wl,-Map,build/{stem}.map',
         'firmware/start.S','firmware/src/sdram_exec_test.c','firmware/sdram_exec_far.S','-o',f'build/{stem}.elf']
    subprocess.run(cmd,cwd=ROOT,check=True)
    segments,metadata=extract(ROOT,stem,str(LLVM/'llvm-objcopy.exe'),str(LLVM/'llvm-nm.exe'))
    if metadata['code_bytes']<=65536:raise RuntimeError('Diagnostic must exceed old instruction-memory capacity')
    package={'format':'soc-game-package','version':1,'app':'sdram-exec-test','segments':segments,'execution':metadata,'required_cpu_features':{'sdram-exec-v1':True}}
    soc.write(ROOT/f'build/{stem}.package.json',json.dumps(package,indent=2)+'\n')
    from load_game import package_segments
    package_segments(ROOT/f'build/{stem}.package.json')
    data=(ROOT/f'build/{stem}.bin').read_bytes().ljust(65536,b'\0')
    if len(data)>65536:raise RuntimeError('Diagnostic local image overflow')
    words=[int.from_bytes(data[i:i+4],'little') for i in range(0,65536,4)]
    soc.write(ROOT/f'build/{stem}.hex',''.join(f'{x:08x}\n' for x in words))
    soc.write(ROOT/f'build/{stem}.mif','WIDTH=32;\nDEPTH=16384;\nADDRESS_RADIX=HEX;\nDATA_RADIX=HEX;\nCONTENT BEGIN\n'+''.join(f'{i:04x} : {x:08x};\n' for i,x in enumerate(words))+'END;\n')
    symbols=subprocess.check_output([str(LLVM/'llvm-nm.exe'),'--defined-only',str(ROOT/f'build/{stem}.elf')],text=True)
    soc.write(ROOT/f'build/{stem}.symbols.json',json.dumps({x.split()[-1]:int(x.split()[0],16) for x in symbols.splitlines() if len(x.split())==3},indent=2)+'\n')
    dis=subprocess.check_output([str(LLVM/'llvm-objdump.exe'),'-d',str(ROOT/f'build/{stem}.elf')],text=True)
    soc.write(OUT/'diagnostic-disassembly.txt',dis)
    print('Diagnostic local/external segments:',[(s['address'],s['bytes']) for s in segments],flush=True)

def fit():
    if not (ROOT/'build/sdram-exec-test.mif').exists():firmware()
    q=(ROOT/'docs/benchmarks/arch-upgrade-001-stage-5/worker/project.qsf').read_text()
    q=q.replace('build/quartus-arch-stage5-worker','build/quartus-sdram-exec')
    q+='\nset_parameter -name ENABLE_SDRAM_EXEC 1\nset_parameter -name MIF_FILE "build/sdram-exec-test.mif"\n'
    for name in ('sdram_instruction_cache','sdram_fetch_arbiter','sdram_execution_bridge'):q+=f'set_global_assignment -name SYSTEMVERILOG_FILE rtl/{name}.sv\n'
    made=[]
    try:
        for suffix,text in [('qsf',q),('qpf','QUARTUS_VERSION = "18.1"\nPROJECT_REVISION = "'+NAME+'"\n')]:
            p=ROOT/(NAME+'.'+suffix)
            if p.exists():raise RuntimeError('Refusing to overwrite '+str(p))
            p.write_text(text,encoding='utf-8');made.append(p)
        soc.write(OUT/'project.qsf',q)
        fit_inputs=soc.sources(True)+[ROOT/'fpga/soc.sdc',ROOT/'build/sdram-exec-test.mif']
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in fit_inputs}
        soc.write(OUT/'fit-input-hashes.json',json.dumps(source_hashes,indent=2)+'\n')
        qt=Path('C:/intelFPGA_lite/18.1/quartus/bin64')
        for stage in ('map','fit','sta','asm'):
            with (OUT/('quartus-'+stage+'.log')).open('w',encoding='utf-8') as log:
                subprocess.run([str(qt/('quartus_'+stage+'.exe')),NAME],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            print('Quartus',stage,'passed',flush=True)
            if stage=='sta':timing_gate(FIT,NAME)
        for name,digest in source_hashes.items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Source changed during fit: '+name)
        soc.write(OUT/'fit-identity.json',json.dumps({'file':str((FIT/(NAME+'.sof')).relative_to(ROOT)),'sha256':hashlib.sha256((FIT/(NAME+'.sof')).read_bytes()).hexdigest(),'cpu_features':0x80000007,'gpu_features':3},indent=2)+'\n')
    finally:
        for p in made:p.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('firmware','fit'));a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    firmware() if a.action=='firmware' else fit()
