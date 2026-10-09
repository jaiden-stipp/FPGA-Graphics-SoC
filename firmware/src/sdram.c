#include "sdram.h"
#include "soc.h"
#ifndef SDRAM_RETENTION_CYCLES
#define SDRAM_RETENTION_CYCLES 5000000u
#endif
// Test all 32 data lines and all 25 word-address lines without touching assets.
// Address alias test saves/restores original words, then tests byte masks and
// signed subword reads in the reserved high page. Refresh runs during retention.
uint32_t sdram_self_test(void) {
    volatile uint32_t *const end=(volatile uint32_t *)(uintptr_t)0x87fffffcu;
    uint32_t saved[26];
    saved[0]=*end;
    for (uint32_t bit=0;bit<25;++bit) {
        volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(0x87fffffcu^(4u<<bit));
        saved[bit+1]=*p;
    }
    for (uint32_t bit=0;bit<32;++bit) {
        uint32_t v=1u<<bit; *end=v;
        if (*end!=v) return 0xdead1000u+bit;
        *end=~v; if (*end!=~v) return 0xdead1040u+bit;
    }
    *end=0xa55a5aa5u;
    for (uint32_t bit=0;bit<25;++bit) {
        volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(0x87fffffcu^(4u<<bit));
        *p=0x12340000u+bit;
    }
    if (*end!=0xa55a5aa5u) return 0xdead1080u;
    for (uint32_t bit=0;bit<25;++bit) {
        volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(0x87fffffcu^(4u<<bit));
        if (*p!=0x12340000u+bit) return 0xdead1090u+bit;
    }
    for (uint32_t bit=0;bit<25;++bit) {
        volatile uint32_t *p=(volatile uint32_t *)(uintptr_t)(0x87fffffcu^(4u<<bit));
        *p=saved[bit+1];
    }
    volatile uint8_t *bytes=(volatile uint8_t *)end;
    *end=0x12345678u; bytes[0]=0x80; bytes[1]=0xfe; bytes[2]=0x81; bytes[3]=0x95;
    if (*end!=0x9581fe80u) return 0xdead10c0u;
    if (*(volatile int8_t *)bytes!=-128 || bytes[1]!=254) return 0xdead10c1u;
    volatile uint16_t *halves=(volatile uint16_t *)end;
    halves[0]=0x8123; halves[1]=0xabcd;
    if (*end!=0xabcd8123u || *(volatile int16_t *)halves!=-32477 || halves[1]!=0xabcd)
        return 0xdead10c2u;
    *end=0x5aa5c33cu;
    uint32_t start=SOC_CYCLES;
    while ((uint32_t)(SOC_CYCLES-start)<SDRAM_RETENTION_CYCLES) { }
    if (*end!=0x5aa5c33cu) return 0xdead10d0u;
    *end=saved[0];
    return 0x5dad600du;
}
