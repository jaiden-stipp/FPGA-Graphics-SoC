"""Build audited CPU/geometry-worker equivalence firmware from the oracle inputs."""
import json,subprocess,re,hashlib
import soc
from rv32i_subset import check,instruction_words
from sm64_engine_slice import llvm_tool

def build():
    out=soc.ROOT/'build/arch-stage5';cases=json.loads((out/'vectors.json').read_text())
    rows=['#include "geometry_worker.h"',
          'typedef struct {int16_t view[12],origin[3];int32_t position[3];uint32_t first,count;} geometry_probe_case_t;',
          'static const scene_vertex_t geometry_vertices[]={']
    for c in cases:
        rows+=['{'+','.join(map(str,v))+'},' for v in c['vertices']]
    rows+=['};','static const geometry_probe_case_t geometry_cases[]={']
    first=0
    for c in cases:
        rows+=['{'+','.join('{'+','.join(map(str,c[k]))+'}' for k in ('view','origin','position'))+f",{first},{len(c['vertices'])}"+'},']
        first+=len(c['vertices'])
    rows+=['};'];(soc.ROOT/'firmware/generated/geometry_probe_data.h').write_text('\n'.join(rows)+'\n')
    flags=['-DSOC_GEOMETRY_OFFLOAD','-DSOC_INTEGER_MUL']
    check(soc.ROOT/'firmware/tests/geometry_probe.c',str(llvm_tool('clang')),additional_api={'transform','plane','geometry_transform','player_bind_query','player_floor_index'},extra_flags=flags)
    cmd=[str(llvm_tool('clang')),'--target=riscv32-unknown-elf','-fuse-ld=lld','-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax','-O1','-ffreestanding','-fno-builtin','-nostdlib','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Ifirmware/include','-Ifirmware/generated','-Wl,-T,firmware/link.ld','-Wl,--no-relax','-Wl,--gc-sections',*flags,'firmware/start.S','firmware/tests/geometry_probe.c','firmware/src/player.c','firmware/rv32i_builtins.S','-o',str(out/'probe.elf')]
    subprocess.run(cmd,cwd=soc.ROOT,check=True)
    subprocess.run([str(llvm_tool('llvm-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
    data=(out/'probe.bin').read_bytes();padded=data.ljust((len(data)+3)//4*4,b'\0')
    (out/'probe.hex').write_text(''.join(f'{int.from_bytes(padded[i:i+4],"little"):08x}\n' for i in range(0,len(padded),4)))
    dis=subprocess.check_output([str(llvm_tool('llvm-objdump')),'-d',str(out/'probe.elf')],text=True);(out/'probe-disassembly.txt').write_text(dis)
    audited=muls=0
    for address,ins in instruction_words(dis):
        audited+=1
        if ins&127 not in (3,35,19,51,55,23,111,103,99):raise ValueError('Unsupported opcode')
        if ins&127==51 and ins>>25==1:
            if (ins>>12)&7:raise ValueError('Only MUL is supported')
            muls+=1
        elif ins&127==51 and ins>>25 not in (0,32):raise ValueError('Unsupported arithmetic')
    if not audited:raise ValueError('Empty ISA audit')
    nm=subprocess.check_output([str(llvm_tool('llvm-nm')),'--defined-only',str(out/'probe.elf')],text=True)
    symbols={m[3]:int(m[1],16) for line in nm.splitlines() if(m:=re.fullmatch(r'([0-9a-fA-F]+)\s+(\w)\s+(\S+)',line))}
    spec={'format':'soc-game-package','version':1,'required_cpu_features':{'mul':True,'geometry-worker-v1':True},'segments':[{'file':'probe.bin','address':0,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
    (out/'probe.package.json').write_text(json.dumps(spec,indent=2)+'\n')
    (out/'probe-build.json').write_text(json.dumps({'command':cmd,'symbols':symbols,'audited_instructions':audited,'mul_instructions':muls,'package':spec},indent=2)+'\n')
    print('Audited geometry probe:',audited,'instructions;',muls,'MUL instructions')

if __name__=='__main__':build()
