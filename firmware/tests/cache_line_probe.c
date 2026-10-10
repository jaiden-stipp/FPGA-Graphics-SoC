// Identical RV32I binary for every cache-line experiment. Never modifies assets.
#include "soc.h"
#include "world.h"
#include "cache_line_probe_config.h"
typedef struct {uint32_t cycles,hits,misses,fill_words,sum;} measurement_t;
volatile measurement_t line_results[6];
volatile uint32_t line_clock;
static uint32_t bc,bh,bm,bf;
static void begin(void){bh=SOC_CACHE_READ_HITS;bm=SOC_CACHE_READ_MISSES;bf=SOC_CACHE_FILL_WORDS;bc=SOC_CYCLES;}
static void end(uint32_t i,uint32_t sum){uint32_t elapsed=SOC_CYCLES-bc;line_results[i].cycles=elapsed;line_results[i].hits=SOC_CACHE_READ_HITS-bh;line_results[i].misses=SOC_CACHE_READ_MISSES-bm;line_results[i].fill_words=SOC_CACHE_FILL_WORDS-bf;line_results[i].sum=sum;}
static uint32_t fold(uint32_t h,int32_t v){return (h<<5)-h+(uint32_t)v;}
static uint32_t collision(void){
 const world_area_t *areas=(const world_area_t *)PROBE_AREAS;
 uint32_t sum=0;
 for(uint32_t a=0;a<PROBE_AREA_COUNT;++a){
  const world_area_t *w=areas+a;player_t p={0};p.y=16000;
  for(uint32_t z=0;z<8;++z)for(uint32_t x=0;x<8;++x){
   p.x=w->grid_x+((int32_t)(((uint32_t)fixed_mul((int32_t)w->grid_width,(int32_t)x))>>3)<<9)+256;
   p.z=w->grid_z+((int32_t)(((uint32_t)fixed_mul((int32_t)w->grid_depth,(int32_t)z))>>3)<<9)+256;
   world_collision(w,&p);sum=fold(sum,player_floor(w->physics,p.x,p.z,16000));
   sum=fold(sum,player_floor_index());
  }
 }
 return sum;
}
static uint32_t geometry(void){
 const world_area_t *areas=(const world_area_t *)PROBE_AREAS;uint32_t sum=0;
 for(uint32_t a=0;a<PROBE_AREA_COUNT;++a){
  const world_area_t *w=areas+a;
  for(uint32_t c=0;c<w->chunk_count;++c){
   const scene_mesh_t *m=&w->chunks[c].mesh;
   for(uint32_t i=0;i<m->vertex_count;++i){const scene_vertex_t *v=m->vertices+i;sum=fold(sum,v->x);sum=fold(sum,v->y);sum=fold(sum,v->z);}
   for(uint32_t i=0;i<m->triangle_count;++i){const scene_triangle_t *t=m->triangles+i;sum=fold(sum,t->a);sum=fold(sum,t->b);sum=fold(sum,t->c);sum=fold(sum,t->color);}
  }
 }
 return sum;
}
static uint32_t sparse(void){volatile const uint32_t *p=(const uint32_t *)0x80000000u;uint32_t sum=0;for(uint32_t i=0;i<64;++i)sum=fold(sum,(int32_t)p[i<<3]);return sum;}
static void evict(void){volatile const uint32_t *p=(const uint32_t *)0x87ffe000u;for(uint32_t i=0;i<1024;++i){uint32_t v=p[i];(void)v;}}
int main(void){
 line_clock=SOC_CLOCK_HZ;SOC_SCRATCH=0x11ce0000u;evict();
 for(uint32_t i=0;i<2;++i){begin();uint32_t sum=collision();end(i,sum);}
 evict();for(uint32_t i=2;i<4;++i){begin();uint32_t sum=geometry();end(i,sum);}
 evict();for(uint32_t i=4;i<6;++i){begin();uint32_t sum=sparse();end(i,sum);}
 SOC_SCRATCH=0x11ce600du;for(;;){}
}
