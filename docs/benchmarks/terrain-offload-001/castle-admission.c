
#include <stddef.h>
#include <stdint.h>
#define SOC_H
#define SOC_CYCLES 0u
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n);
#define PORTABLE_DATA_DEFINE
#include "portable_data.h"
#include "castle_surface_types.h"
#include "C:/Users/Orb1t/Documents/Codex/FPGA-Game-SoC/firmware/src/world.c"
#include "C:/Users/Orb1t/Documents/Codex/FPGA-Game-SoC/firmware/ports/castle.c"
void *memcpy(void *d,const void *s,size_t n){unsigned char *a=d;const unsigned char *b=s;for(size_t i=0;i<n;++i)a[i]=b[i];return d;}
int gfx_command(uint8_t op,const uint8_t *p,uint8_t n){(void)op;(void)p;(void)n;return 0;}
int gfx_define_mesh(uint8_t h,uint16_t v,uint16_t t){(void)h;(void)v;(void)t;return 0;}
int gfx_draw_matrix(uint8_t h,const int16_t m[12]){(void)h;(void)m;return 0;}
int gfx_identity_view(void){return 0;}
int gfx_begin_frame(uint32_t f){(void)f;return 0;}
int gfx_end_frame(void){return 0;}
uint32_t probe(int32_t *out){
    if(game_port_init())return 0;
    for(uint32_t i=0;i<40;++i)game_port_update(0);
    out[0]=player.x;out[1]=player.y;out[2]=player.z;
    for(uint32_t i=0;i<12;++i)out[3+i]=view.view[i];
    const world_area_t *a=world_areas+current_area;
    for(uint32_t i=0;i<a->chunk_count;++i){const world_chunk_t *ch=a->chunks+i;uint32_t b=15+4*i;int16_t m[12];
        out[b]=safe_matrix(ch,&player,view.view,m);out[b+1]=0;out[b+2]=0;
        for(uint32_t row=0;row<3;++row){uint32_t k=4*row;
            int32_t sum=fixed_mul((ch->origin[0]-player.x)*4,view.view[k])+fixed_mul((ch->origin[1]-player.y)*4,view.view[k+1])+fixed_mul((ch->origin[2]-player.z)*4,view.view[k+2]);
            if(sum&255)out[b+1]=1;
        }
        int32_t lo[3]={2147483647,2147483647,2147483647},hi[3]={-2147483647,-2147483647,-2147483647};
        for(uint32_t j=0;j<8;++j){clip_point_t q=transform(ch->bounds[j&1],ch->bounds[2+((j>>1)&1)],ch->bounds[4+((j>>2)&1)],&player,view.view);int32_t v[3]={q.x,q.y,q.z};
            for(uint32_t k=0;k<3;++k){if(v[k]<lo[k])lo[k]=v[k];if(v[k]>hi[k])hi[k]=v[k];}}
        out[b+2]=lo[2]<257 || hi[2]>30000 || lo[0]<-32764 || hi[0]>32764 || lo[1]<-32764 || hi[1]>32764 ||
            lo[0]*256+lo[2]*160<0 || -hi[0]*256+lo[2]*160<0 || lo[1]*256+lo[2]*120<0 || -hi[1]*256+lo[2]*120<0;
        out[b+3]=bounds_valid(ch);
    }return a->chunk_count;
}
