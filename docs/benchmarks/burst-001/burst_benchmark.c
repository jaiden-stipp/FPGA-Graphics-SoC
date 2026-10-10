#include "soc.h"
typedef struct {uint32_t cycles,hits,misses,fill_words,sum;} measurement_t;
volatile measurement_t burst_results[3];
volatile uint32_t burst_errors,burst_clock;
static uint32_t begin_cycles,begin_hits,begin_misses,begin_fills;
static void begin(void){begin_hits=SOC_CACHE_READ_HITS;begin_misses=SOC_CACHE_READ_MISSES;begin_fills=SOC_CACHE_FILL_WORDS;begin_cycles=SOC_CYCLES;}
static void end(uint32_t phase,uint32_t sum){uint32_t elapsed=SOC_CYCLES-begin_cycles;burst_results[phase].cycles=elapsed;burst_results[phase].hits=SOC_CACHE_READ_HITS-begin_hits;burst_results[phase].misses=SOC_CACHE_READ_MISSES-begin_misses;burst_results[phase].fill_words=SOC_CACHE_FILL_WORDS-begin_fills;burst_results[phase].sum=sum;}
int main(void){
 volatile uint32_t *a=(volatile uint32_t *)0x80000000u,*b=(volatile uint32_t *)0x80001000u;
 burst_errors=0;burst_clock=SOC_CLOCK_HZ;SOC_SCRATCH=0xb0170000u;
 for(uint32_t i=0;i<512;++i){a[i]=0x12340000u+i;b[i]=0xabcd0000u+i;}
 uint32_t sum=0;begin();for(uint32_t i=0;i<64;++i)sum+=a[i<<3];end(0,sum);
 sum=0;begin();for(uint32_t i=0;i<512;++i)sum+=a[i];end(1,sum);
 for(uint32_t i=0;i<64;++i){volatile uint32_t v=b[i<<3];(void)v;}
 sum=0;begin();for(uint32_t rep=0;rep<4;++rep)for(uint32_t i=0;i<64;++i){sum+=a[i<<3];sum+=b[i<<3];}end(2,sum);
 for(uint32_t i=0;i<512;++i){if(a[i]!=0x12340000u+i)++burst_errors;if(b[i]!=0xabcd0000u+i)++burst_errors;}
 SOC_SCRATCH=burst_errors?0xdeadb017u:0xb017600du;for(;;){}
}
