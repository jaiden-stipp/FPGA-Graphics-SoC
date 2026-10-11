// Measurement-only: unchanged packed transport versus contiguous RAM staging.
// No optional per-command profiling; all CRC bytes use actual gfx.c crc_byte.
#include "soc.h"
#include "gfx_staging_input.h"
#define GFX_PACKED
#include "../src/gfx.c"
typedef struct {uint32_t cycles,retired,freezes,bubbles,redirects,writes,busy,hits,misses,fills,bytes,words,hash,error,index,reserved;} result_t;
volatile result_t staging_results[PROBE_FRAMES*3];
volatile uint32_t staging_done,staging_clock;
static volatile uint32_t ram_buffer[(PROBE_MAX_BYTES+3)/4];
static volatile uint32_t *destination;
static uint32_t staged_word,staged_count,staged_bytes,staged_words;
static uint32_t before[10];
static void snapshot(uint32_t *v) {
 SOC_CPU_SNAPSHOT=1;
 v[0]=SOC_CPU_RETIRED;v[1]=SOC_CPU_FREEZES;v[2]=SOC_CPU_BUBBLES;v[3]=SOC_CPU_REDIRECTS;
 v[4]=SOC_CACHE_WRITE_REQUESTS;v[5]=SOC_CACHE_BUSY_CYCLES;v[6]=SOC_CACHE_READ_HITS;
 v[7]=SOC_CACHE_READ_MISSES;v[8]=SOC_CACHE_FILL_WORDS;
}
static void stage_byte(uint8_t b) {
 staged_word|=(uint32_t)b<<(staged_count<<3);++staged_count;++staged_bytes;
 if(staged_count==4){destination[staged_words++]=staged_word;staged_word=0;staged_count=0;}
}
static int stage_command(uint8_t op,const uint8_t *p,uint8_t length) {
 uint8_t header[5]={GFX_MAGIC_0,GFX_MAGIC_1,GFX_VERSION,op,length};uint16_t crc=0xffffu;
 for(uint32_t i=0;i<5;++i){crc=crc_byte(crc,header[i]);stage_byte(header[i]);}
 for(uint32_t i=0;i<length;++i){crc=crc_byte(crc,p[i]);stage_byte(p[i]);}
 stage_byte((uint8_t)(crc>>8));stage_byte((uint8_t)crc);return 0;
}
static int replay(uint32_t offset,uint32_t length,uint32_t staging) {
 const uint8_t *p=replay_input+offset;uint32_t used=0;
 while(used<length){uint32_t n=p[4];int result;
  if(staging)result=stage_command(p[3],p+5,(uint8_t)n);
  else result=gfx_command(p[3],p+5,(uint8_t)n);
  if(result)return result;p+=n+7;used+=n+7;
 }
 if(staging && staged_count){destination[staged_words++]=staged_word;staged_word=0;staged_count=0;}
 return 0;
}
static uint32_t verify(uint32_t offset,uint32_t length) {
 volatile uint8_t *p=(volatile uint8_t *)destination;uint32_t h=0;
 for(uint32_t i=0;i<length;++i){uint32_t b=p[i];if(b!=replay_input[offset+i])return 0xffffffffu;h=(h<<5)-h+b;}
 return h;
}
int main(void) {
 staging_clock=SOC_CLOCK_HZ;
 if(!(SOC_GPU_FEATURES&SOC_GPU_FEATURE_PACKED)){SOC_SCRATCH=0xdead2b01u;for(;;){}}
 if(replay(0,PROBE_PREFIX,0)){SOC_SCRATCH=0xdead2b02u;for(;;){}}
 for(uint32_t f=0;f<PROBE_FRAMES;++f)for(uint32_t mode=0;mode<3;++mode){
  uint32_t idx=f*3+mode;volatile result_t *r=staging_results+idx;
  destination=mode==2?(volatile uint32_t *)(uintptr_t)0x87ff0000u:ram_buffer;
  staged_word=0;staged_count=0;staged_bytes=0;staged_words=0;
  snapshot(before);uint32_t start=SOC_CYCLES;
  int error=replay(frame_offsets[f],frame_lengths[f],mode);
  uint32_t elapsed=SOC_CYCLES-start;uint32_t after[10];snapshot(after);
  r->cycles=elapsed;r->retired=after[0]-before[0];r->freezes=after[1]-before[1];r->bubbles=after[2]-before[2];r->redirects=after[3]-before[3];
  r->writes=after[4]-before[4];r->busy=after[5]-before[5];r->hits=after[6]-before[6];r->misses=after[7]-before[7];r->fills=after[8]-before[8];
  r->bytes=mode?staged_bytes:frame_lengths[f];r->words=mode?staged_words:0;r->index=idx;r->error=error!=0;
  if(mode){r->hash=verify(frame_offsets[f],frame_lengths[f]);if(r->hash!=frame_hashes[f] || staged_bytes!=frame_lengths[f] || staged_words!=(frame_lengths[f]+3)/4)r->error=1;}
  else if(gfx_wait_frame(frame_ids[f]))r->error=1;
  if(r->error){SOC_SCRATCH=0xdead2b10u+idx;for(;;){}}
  staging_done=idx+1;
 }
 SOC_SCRATCH=0x2b00600du;for(;;){}
}
