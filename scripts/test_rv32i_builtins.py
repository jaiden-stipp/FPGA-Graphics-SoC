"""Execute the actual software multiply ABI helper on the production CPU RTL."""
import random,shutil,subprocess,unittest
from types import SimpleNamespace
import soc

class Builtins(unittest.TestCase):
    def test_software_multiply_on_cpu(self):
        out=soc.BUILD/'builtins-test';out.mkdir(parents=True,exist_ok=True)
        rng=random.Random(0x52563332)
        edge=[0,1,2,0x7fffffff,0x80000000,0xffffffff]
        pairs=[(a,b) for a in edge for b in edge]+[(rng.getrandbits(32),rng.getrandbits(32)) for _ in range(128)]
        source=out/'probe.c'
        source.write_text('#include <stdint.h>\nextern uint32_t __mulsi3(uint32_t,uint32_t);\n'
            'static const uint32_t cases[][3]={'+','.join('{%su,%su,%su}'%(a,b,(a*b)&0xffffffff) for a,b in pairs)+'};\n'
            'int main(void){volatile uint32_t *scratch=(volatile uint32_t *)0x40000018u;'
            'for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);++i)'
            'if(__mulsi3(cases[i][0],cases[i][1])!=cases[i][2]){*scratch=0xdead0001u;for(;;){}}'
            '*scratch=0x600db17u;for(;;){}}\n')
        elf=out/'probe.elf';binary=out/'probe.bin'
        subprocess.run([soc.tool('clang'),'--target=riscv32-unknown-elf','-fuse-ld=lld',
            '-march=rv32i','-mabi=ilp32','-msmall-data-limit=0','-mno-relax','-O1',
            '-ffreestanding','-nostdlib','-Wl,--no-relax','-Wl,-T,firmware/link.ld',
            'firmware/start.S',str(source),'firmware/rv32i_builtins.S','-o',str(elf)],cwd=soc.ROOT,check=True)
        subprocess.run([soc.tool('llvm-objcopy'),'-O','binary',str(elf),str(binary)],check=True)
        data=binary.read_bytes();data+=bytes((-len(data))%4)
        words=[int.from_bytes(data[i:i+4],'little') for i in range(0,len(data),4)]
        (out/'probe.hex').write_text(''.join('%08x\n'%word for word in words))
        soc.simulate(SimpleNamespace(simulator='iverilog' if shutil.which('iverilog') else 'modelsim',full=False,tests='cpu_builtins_tb'))

if __name__=='__main__':unittest.main()
