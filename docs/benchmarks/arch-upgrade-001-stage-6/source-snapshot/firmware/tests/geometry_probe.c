// Real CPU/MMIO adapter versus the original production transform and planes.
#include "../src/world.c"
#include "geometry_probe_data.h"
static geometry_point_t expected_points[128],actual_points[128];
static uint8_t expected_codes[128],actual_codes[128];
volatile uint32_t geometry_results[10][4];
int main(void) {
    if(!(SOC_CPU_FEATURES&SOC_FEATURE_GEOMETRY))goto failed;
    for(uint32_t c=0;c<10;++c) {
        const geometry_probe_case_t *t=geometry_cases+c;
        player_t p={0};p.x=t->position[0];p.y=t->position[1];p.z=t->position[2];
        uint32_t start=SOC_CYCLES;
        for(uint32_t i=0;i<t->count;++i) {
            const scene_vertex_t *s=geometry_vertices+t->first+i;
            expected_points[i]=transform(s->x+t->origin[0],s->y+t->origin[1],s->z+t->origin[2],&p,t->view);
            uint8_t code=0;
            for(uint32_t k=0;k<6;++k)if(plane(expected_points[i],k)<0)code|=(uint8_t)(1u<<k);
            expected_codes[i]=code;
        }
        geometry_results[c][0]=SOC_CYCLES-start;
        start=SOC_CYCLES;
        if(geometry_transform(geometry_vertices+t->first,t->count,t->origin,t->position,t->view,actual_points,actual_codes)!=1)goto failed;
        geometry_results[c][1]=SOC_CYCLES-start;
        geometry_results[c][2]=GW_REG(0x90);geometry_results[c][3]=GW_REG(0x94);
        for(uint32_t i=0;i<t->count;++i) {
            if(expected_points[i].x!=actual_points[i].x || expected_points[i].y!=actual_points[i].y ||
               expected_points[i].z!=actual_points[i].z || expected_codes[i]!=actual_codes[i]) {
                SOC_SCRATCH=0xdead5000u+c;return -1;
            }
        }
    }
    SOC_SCRATCH=0x3500600du;return 0;
failed:
    SOC_SCRATCH=0xdead50ffu;return -1;
}
