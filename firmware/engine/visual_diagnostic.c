#include "engine_slice.h"
#include "sm64.h"
#include "soc.h"
#include "visual.inc"
volatile uint32_t visual_trace[96][32];
volatile uint32_t visual_report[8]={0x56495301u};
static int16_t pose[ENGINE_VISUAL_VERTICES*3],view[12];
static uint32_t hash(const int16_t *p,uint32_t count){
    uint32_t h=2166136261u;
    for(uint32_t i=0;i<count;++i){uint16_t v=(uint16_t)p[i];h=(h^(v&255u))*16777619u;h=(h^(v>>8))*16777619u;}
    return h;
}
int main(void){
    int32_t spawn[3]={-1328,260,4664};uint32_t start=SOC_CYCLES;
    sm64_engine_init(spawn);visual_report[1]=SOC_CYCLES-start;
    for(uint32_t tick=0;tick<96;++tick){
        uint32_t buttons=tick<8?0u:tick<20?4u:tick<27?20u:tick<42?4u:0u;
        if(tick==48)buttons|=ENGINE_CAMERA_RIGHT;if(tick==72)buttons|=ENGINE_CAMERA_DOWN;
        engine_result_t result;start=SOC_CYCLES;
        sm64_engine_update(buttons,ENGINE_USE_CAMERA_YAW,&result);visual_trace[tick][0]=SOC_CYCLES-start;
        start=SOC_CYCLES;sm64_engine_camera_step(view,4);visual_trace[tick][1]=SOC_CYCLES-start;
        start=SOC_CYCLES;int fault=sm64_engine_pose(pose,ENGINE_VISUAL_VERTICES,4);visual_trace[tick][2]=SOC_CYCLES-start;
        visual_trace[tick][3]=sm64_engine_probe(0);visual_trace[tick][4]=result.action;
        for(uint32_t k=0;k<3;++k)visual_trace[tick][5+k]=sm64_engine_probe(2+k);
        for(uint32_t k=0;k<10;++k)visual_trace[tick][8+k]=sm64_engine_visual_probe(k);
        visual_trace[tick][18]=hash(pose,ENGINE_VISUAL_VERTICES*3);visual_trace[tick][19]=hash(view,12);
        for(uint32_t k=0;k<12;++k)visual_trace[tick][20+k]=(int32_t)view[k];
        if(fault || visual_trace[tick][3]){visual_report[2]=fault?0x204:visual_trace[tick][3];break;}
        visual_report[3]=tick+1;
    }
    visual_report[4]=ENGINE_VISUAL_VERTICES;visual_report[5]=ENGINE_VISUAL_JOINTS;
#ifdef SOC_STACK_CANARY
    extern uint32_t _local_bss_end,_stack_top;volatile uint32_t *p=&_local_bss_end;
    while(p<&_stack_top && *p==0xa55a3cc3u)++p;
    visual_report[6]=(uint32_t)((uintptr_t)&_stack_top-(uintptr_t)p);
#endif
    SOC_REG(0x18)=visual_report[2]?0xdead00e2u:0x5641600du;
    for(;;){}
}
