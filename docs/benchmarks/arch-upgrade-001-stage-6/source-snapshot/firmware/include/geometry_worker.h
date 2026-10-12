#ifndef GEOMETRY_WORKER_H
#define GEOMETRY_WORKER_H
#include "assets.h"
#include "soc.h"
typedef struct {int32_t x,y,z;} geometry_point_t;
#define SOC_FEATURE_GEOMETRY 2u
#define GW_REG(offset) SOC_REG(0x100u+(offset))

#ifdef SOC_GEOMETRY_OFFLOAD
// Return 0 on old hardware (no MMIO probe), 1 on complete ordered output,
// -1 on protocol failure. CPU/cache owns source data and render scratch memory.
static inline int geometry_transform(const scene_vertex_t *vertices,uint32_t count,
    const int16_t origin[3],const int32_t position[3],const int16_t view[12],
    geometry_point_t *points,uint8_t *codes) {
    if(!(SOC_CPU_FEATURES&SOC_FEATURE_GEOMETRY))return 0;
    if(!count || count>128 || GW_REG(0)!=0x47570101u)return -1;
    GW_REG(0x64)=2u;
    for(uint32_t i=0;i<12;++i)GW_REG(0x10u+(i<<2))=(uint32_t)(int32_t)view[i];
    for(uint32_t i=0;i<3;++i) {
        GW_REG(0x40u+(i<<2))=(uint32_t)position[i];
        GW_REG(0x50u+(i<<2))=(uint32_t)(int32_t)origin[i];
    }
    GW_REG(0x60)=count;GW_REG(0x64)=1u;
    uint32_t pushed=0,completed=0;
    // At most four outstanding inputs: consuming one result always grants
    // room for its replacement. No unbounded write/poll deadlock.
    uint32_t initial=count<4?count:4;
    while(pushed<initial) {
        const scene_vertex_t *s=vertices+pushed;
        GW_REG(0x70)=(uint32_t)(uint16_t)s->x|((uint32_t)(uint16_t)s->y<<16);
        GW_REG(0x74)=(uint32_t)(int32_t)s->z;++pushed;
    }
    while(completed<count) {
        uint32_t status;
        do { status=GW_REG(4);if(status&2u)goto failed; } while(!(status&0xff00u));
        points[completed].x=(int32_t)GW_REG(0x80);
        points[completed].y=(int32_t)GW_REG(0x84);
        points[completed].z=(int32_t)GW_REG(0x88);
        codes[completed]=(uint8_t)GW_REG(0x8c);++completed;
        if(pushed<count) {
            const scene_vertex_t *s=vertices+pushed;
            GW_REG(0x70)=(uint32_t)(uint16_t)s->x|((uint32_t)(uint16_t)s->y<<16);
            GW_REG(0x74)=(uint32_t)(int32_t)s->z;++pushed;
        }
    }
    if((GW_REG(4)&3u) || GW_REG(8)!=count || GW_REG(12)!=count)goto failed;
    return 1;
failed:
    GW_REG(0x64)=2u;
    return -1;
}
#endif
#endif
