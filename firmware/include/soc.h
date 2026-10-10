#ifndef SOC_H
#define SOC_H
#include <stdint.h>
#define SOC_REG(offset) (*(volatile uint32_t *)(uintptr_t)(0x40000000u + (offset)))
#define GFX_DATA       SOC_REG(0x00)
#define GFX_STATUS     SOC_REG(0x04)
#define GFX_FREE       SOC_REG(0x08)
#define GFX_FRAME_ID   SOC_REG(0x0c)
#define GFX_ACK        SOC_REG(0x10)
#define GFX_ERRORS     SOC_REG(0x14)
#define SOC_SCRATCH    SOC_REG(0x18)
#define SOC_ID         SOC_REG(0x1c)
#define SOC_BUTTONS    SOC_REG(0x54)
#define SOC_CYCLES     SOC_REG(0x58)
#define SOC_CLOCK_HZ   SOC_REG(0x5c)
#define SOC_INPUT_ABI  SOC_REG(0x64)
#define SOC_CACHE_ABI  SOC_REG(0x68)
#define SOC_CACHE_READ_HITS SOC_REG(0x6c)
#define SOC_CACHE_READ_MISSES SOC_REG(0x70)
#define SOC_CACHE_FILL_WORDS SOC_REG(0x74)
#define SOC_CACHE_WRITE_REQUESTS SOC_REG(0x78)
#define SOC_CACHE_BUSY_CYCLES SOC_REG(0x7c)
#define SOC_CPU_ABI SOC_REG(0x80)
#define SOC_CPU_SNAPSHOT SOC_REG(0x98)
#define SOC_CPU_CYCLES SOC_REG(0x84)
#define SOC_CPU_RETIRED SOC_REG(0x88)
#define SOC_CPU_FREEZES SOC_REG(0x8c)
#define SOC_CPU_BUBBLES SOC_REG(0x90)
#define SOC_CPU_REDIRECTS SOC_REG(0x94)
#define SOC_GPU_STATUS_READS SOC_REG(0xa0)
#define SOC_GPU_FULL_READS SOC_REG(0xa4)
#define BUTTON_LEFT    1u
#define BUTTON_RIGHT   2u
#define BUTTON_FORWARD 4u
#define BUTTON_BACK    8u
#define BUTTON_RESET_VIEW 16u
#define GFX_STAT(n)    SOC_REG(0x20u + 4u * (n))
#define GFX_TX_READY   1u
#define GFX_FRAME_DONE 4u
int gfx_command(uint8_t opcode, const uint8_t *payload, uint8_t length);
int gfx_wait_frame(uint32_t frame_id);
#endif
