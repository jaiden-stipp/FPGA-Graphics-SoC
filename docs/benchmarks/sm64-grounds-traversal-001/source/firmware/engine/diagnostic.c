#include "engine_slice.h"
#include "soc.h"
// Fixed input replay shared with the native reference. No render work is included.
volatile uint32_t engine_trace[96][12];
volatile uint32_t engine_report[8]={0x454e4701u};
int main(void){
    int32_t position[3]={-1328,260,4664};uint32_t start=SOC_CYCLES;
    sm64_engine_init(position);engine_report[1]=SOC_CYCLES-start;
    for(uint32_t tick=0;tick<96;++tick){
        uint32_t buttons=tick<8?0u:(tick<20?4u:(tick<27?20u:(tick<42?4u:0u)));
        SOC_CPU_SNAPSHOT=1u;
        uint32_t cycles=SOC_CPU_CYCLES,retired=SOC_CPU_RETIRED,freezes=SOC_CPU_FREEZES,bubbles=SOC_CPU_BUBBLES;
        uint32_t hits=SOC_REG(0xf4),misses=SOC_REG(0xf8),fills=SOC_REG(0xfc);engine_result_t result;
        sm64_engine_update(buttons,0,&result);
        SOC_CPU_SNAPSHOT=1u;
        engine_trace[tick][5]=SOC_CPU_CYCLES-cycles;engine_trace[tick][6]=SOC_CPU_RETIRED-retired;
        engine_trace[tick][7]=SOC_CPU_FREEZES-freezes;engine_trace[tick][8]=SOC_CPU_BUBBLES-bubbles;
        engine_trace[tick][9]=SOC_REG(0xf4)-hits;engine_trace[tick][10]=SOC_REG(0xf8)-misses;engine_trace[tick][11]=SOC_REG(0xfc)-fills;
        engine_trace[tick][0]=sm64_engine_probe(2);engine_trace[tick][1]=sm64_engine_probe(3);engine_trace[tick][2]=sm64_engine_probe(4);
        engine_trace[tick][3]=result.action;engine_trace[tick][4]=result.fault;
        if(result.fault){engine_report[2]=result.fault;break;}
        engine_report[3]=tick+1;
    }
    engine_report[4]=sm64_engine_probe(5);engine_report[5]=sm64_engine_probe(6);engine_report[6]=sm64_engine_probe(7);
#ifdef SOC_STACK_CANARY
    extern uint32_t _local_bss_end,_stack_top;volatile uint32_t *p=&_local_bss_end;
    while(p<&_stack_top && *p==0xa55a3cc3u)++p;
    engine_report[7]=(uint32_t)((uintptr_t)&_stack_top-(uintptr_t)p);
#endif
    SOC_REG(0x18)=engine_report[2]?0xdead00e1u:0xe061600du;
    for(;;){}
}
