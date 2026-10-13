#include "soc.h"
extern uint32_t far_step(uint32_t value);
volatile uint32_t diagnostic_record[10];
volatile uint32_t initialized_value=0x12345678u;
volatile uint32_t zero_value;
__attribute__((section(".local_bss"))) volatile uint32_t local_zero;
__attribute__((section(".local_data"))) volatile uint32_t local_initialized=0x89abcdefu;
__attribute__((section(".text.local"),noinline))
static uint32_t local_step(uint32_t value) { return value ^ initialized_value; }
int main(void) {
    uint32_t start=SOC_CYCLES,checksum=0;
    if(zero_value || local_zero || initialized_value!=0x12345678u || local_initialized!=0x89abcdefu)goto failed;
    volatile uint8_t *bytes=(volatile uint8_t *)&zero_value;
    bytes[0]=0x80;bytes[1]=0xfe;bytes[2]=0x81;bytes[3]=0x95;
    if(zero_value!=0x9581fe80u || *(volatile int8_t *)bytes!=-128)goto failed;
    volatile uint16_t *halves=(volatile uint16_t *)&zero_value;
    halves[0]=0x8123;halves[1]=0xabcd;
    if(zero_value!=0xabcd8123u || *(volatile int16_t *)halves!=-32477)goto failed;
    for(uint32_t n=0;n<32;++n) {
        uint32_t v=far_step(n*4u);
        if(v!=n*4u+4u)goto failed;
        checksum^=local_step(v);
    }
    if(GFX_ERRORS)goto failed;
    diagnostic_record[0]=SOC_CYCLES-start;
    diagnostic_record[1]=SOC_ICACHE_ABI;
    diagnostic_record[2]=SOC_ICACHE_HITS;
    diagnostic_record[3]=SOC_ICACHE_MISSES;
    diagnostic_record[4]=SOC_ICACHE_FILL_WORDS;
    diagnostic_record[5]=SOC_CPU_FEATURES;
    diagnostic_record[6]=checksum;
    diagnostic_record[7]=zero_value;
    diagnostic_record[8]=local_initialized;
    diagnostic_record[9]=0x5eec600du;
    SOC_SCRATCH=0x5eec600du;
    for(;;) { }
failed:
    SOC_SCRATCH=0xdead60e1u;
    for(;;) { }
}
