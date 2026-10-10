#include <stdint.h>
#define REG(o) (*(volatile uint32_t *)(0x40000000u+(o)))
volatile uint32_t probe_cache_abi,probe_crc,probe_errors,probe_words;
static uint16_t crc_byte(uint16_t crc,uint8_t byte) {
 static const uint16_t t[16]={0,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef};
 uint16_t m=(uint16_t)(crc^((uint16_t)byte<<8));
 uint16_t a=(uint16_t)((m<<4)^t[m>>12]);return (uint16_t)((a<<4)^t[a>>12]);
}
int main(void) {
 probe_cache_abi=REG(0x68);probe_errors=0;probe_words=0;uint16_t crc=0xffff;
 for(uint32_t i=0;i<220781u;++i) {
  volatile uint32_t *p=(volatile uint32_t *)(0x80000000u+(i<<2));uint32_t first=*p;
  uint32_t j=i+1024u;if(j>=220781u)j-=220781u;
  volatile uint32_t other=*(volatile uint32_t *)(0x80000000u+(j<<2));(void)other;
  uint32_t second=*p;volatile uint8_t *b=(volatile uint8_t *)p;uint32_t assembled=0;
  for(uint32_t k=0;k<4;++k){uint8_t v=b[k];assembled|=(uint32_t)v<<(k<<3);crc=crc_byte(crc,v);}
  volatile uint16_t *h=(volatile uint16_t *)p;uint32_t halves=(uint32_t)h[0]|((uint32_t)h[1]<<16);
  if(first!=second || first!=assembled || first!=halves)++probe_errors;probe_words=i+1;
 }
 probe_crc=crc;REG(0x18)=0xcace0000u|crc;for(;;){}
}
