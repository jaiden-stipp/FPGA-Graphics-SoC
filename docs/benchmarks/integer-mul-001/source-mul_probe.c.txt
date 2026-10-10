#include "soc.h"
volatile uint32_t mul_probe_done,mul_probe_cycles,software_probe_cycles,mul_probe_hash;
static uint32_t operands[512],results[512];
static uint32_t software(uint32_t a,uint32_t b) {
    uint32_t sum=0;
    while(b) { if(b&1u)sum+=a; a<<=1;b>>=1; }
    return sum;
}
static uint32_t hardware(uint32_t a,uint32_t b) {
    uint32_t result;
    __asm__(".insn r 0x33, 0, 1, %0, %1, %2" : "=r"(result) : "r"(a), "r"(b));
    return result;
}
int main(void) {
    if(!(SOC_CPU_FEATURES&SOC_FEATURE_MUL)) { SOC_SCRATCH=0xdead00c2u;return 1; }
    uint32_t seed=0x13579bdfu;
    for(uint32_t i=0;i<512u;++i) {
        seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;operands[i]=seed;
    }
    operands[0]=0;operands[1]=0xffffffffu;
    operands[2]=0x80000000u;operands[3]=0xffffffffu;
    operands[4]=0xffffffffu;operands[5]=0xffffffffu;
    operands[6]=0x7fffffffu;operands[7]=0x7fffffffu;
    uint32_t start=SOC_CYCLES;
    for(uint32_t i=0;i<256u;++i)results[i]=hardware(operands[i<<1],operands[(i<<1)+1u]);
    mul_probe_cycles=SOC_CYCLES-start;
    start=SOC_CYCLES;
    for(uint32_t i=0;i<256u;++i)results[i+256u]=software(operands[i<<1],operands[(i<<1)+1u]);
    software_probe_cycles=SOC_CYCLES-start;
    uint32_t hash=0;
    for(uint32_t i=0;i<256u;++i) {
        uint32_t result=results[i+256u];
        if(result!=results[i]) { SOC_SCRATCH=0xdead0100u+i;return 1; }
        hash=(hash<<1)|(hash>>31);hash^=result;
    }
    mul_probe_hash=hash;
    mul_probe_done=256;SOC_SCRATCH=0x6d750100u;return 0;
}
