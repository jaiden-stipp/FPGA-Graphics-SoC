
#include <stdint.h>
static volatile uint32_t *reg_ptr(uint32_t offset);
static uint32_t buffers[2][256], regs[64], pending, used, descriptors, features;
static uint8_t wire[200000];
#define SOC_REG(offset) (*reg_ptr(offset))
#define GFX_DMA_BUFFER(index) buffers[index]
#define GFX_DMA 1
#include "firmware/src/gfx.c"
static volatile uint32_t *reg_ptr(uint32_t offset) {
 if(pending) {
  uint32_t index=(regs[0xc4/4]-0x87fe0000u)/1024u, n=regs[0xc8/4];
  if(index>1 || n>1024 || used+n>200000)regs[0xd4/4]=2;
  else {
   const uint8_t *p=(const uint8_t *)buffers[index];
   for(uint32_t i=0;i<n;++i)wire[used++]=p[i];
   regs[0xd4/4]=0;regs[0xd8/4]=regs[0xcc/4];++descriptors;
  }
  pending=0;
 }
 if(offset==0xd0)pending=1;
 return &regs[offset/4];
}
void reset(uint32_t capability) {
 for(uint32_t i=0;i<64;++i)regs[i]=0;
 features=capability;regs[0x9c/4]=0x80000001u;regs[0xa8/4]=features;regs[0xc0/4]=0x444d0101;
 pending=used=descriptors=0;
 dma_checked=dma_buffer=dma_size=dma_word=dma_count=dma_words=dma_sequence=dma_active=0;
}
void old_error(void){regs[0xd4/4]=0x102u;}
int append(uint8_t op,const uint8_t *p,uint8_t n){return gfx_command(op,p,n);}
int finish(void){if(dma_publish())return -1;return dma_wait();}
const uint8_t *data(void){return wire;}
uint32_t size(void){return used;}
uint32_t chunks(void){return descriptors;}
