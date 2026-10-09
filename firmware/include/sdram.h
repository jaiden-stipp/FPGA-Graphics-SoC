#ifndef SDRAM_H
#define SDRAM_H
#include <stdint.h>
#define SDRAM_BASE 0x80000000u
#define SDRAM_BYTES 0x08000000u
// Reserved final 4 KiB, beyond the package linker limit.
uint32_t sdram_self_test(void);
#endif
