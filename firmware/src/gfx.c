#include "soc.h"
#include "gfx_protocol.h"

#ifdef SOC_PROFILE
volatile uint32_t gfx_profile_command_cycles, gfx_profile_fifo_cycles;
volatile uint32_t gfx_profile_bytes, gfx_profile_commands;
#endif
static uint16_t crc_byte(uint16_t crc, uint8_t byte) {
    // Two nibble lookups preserve CCITT-FALSE exactly. A 32-byte software
    // table avoids eight bit iterations per byte on the unchanged RV32I CPU.
    static const uint16_t table[16]={0x0000,0x1021,0x2042,0x3063,
        0x4084,0x50a5,0x60c6,0x70e7,0x8108,0x9129,0xa14a,0xb16b,
        0xc18c,0xd1ad,0xe1ce,0xf1ef};
    uint16_t mixed=(uint16_t)(crc^((uint16_t)byte<<8));
    mixed=(uint16_t)((mixed<<4)^table[mixed>>12]);
    return (uint16_t)((mixed<<4)^table[mixed>>12]);
}

#ifdef GFX_BATCHED
static uint32_t tx_budget;
#endif
static int send_byte(uint8_t byte) {
#ifdef SOC_PROFILE
    uint32_t waiting=0, wait_start=0;
#endif
    for (uint32_t tries = 0; tries < 20000000u; ++tries) {
#ifdef GFX_BATCHED
        if (!tx_budget && GFX_ERRORS) return -1;
#else
        if (GFX_ERRORS) return -1;
#endif
#ifdef GFX_BATCHED
        // Only this CPU produces bytes. Consumer pops can only increase free space.
        if (!tx_budget) tx_budget=GFX_FREE;
        if (tx_budget) { --tx_budget;
#else
        if (GFX_STATUS & GFX_TX_READY) {
#endif
#ifdef SOC_PROFILE
            if (waiting) gfx_profile_fifo_cycles += SOC_CYCLES-wait_start;
#endif
            GFX_DATA = byte; return 0;
        }
#ifdef SOC_PROFILE
        if (!waiting) { waiting=1; wait_start=SOC_CYCLES; }
#endif
    }
    return -1;
}

int gfx_command(uint8_t opcode, const uint8_t *payload, uint8_t length) {
#ifdef SOC_PROFILE
    uint32_t start=SOC_CYCLES;
#endif
#ifdef GFX_BATCHED
    tx_budget=0; // Refresh reservation for each command; bounded by FIFO free count.
#endif
    uint8_t header[5] = {GFX_MAGIC_0, GFX_MAGIC_1, GFX_VERSION, opcode, length};
    uint16_t crc = 0xffffu;
    for (unsigned i = 0; i < 5; ++i) {
        crc = crc_byte(crc, header[i]);
        if (send_byte(header[i])) return -1;
    }
    for (unsigned i = 0; i < length; ++i) {
        crc = crc_byte(crc, payload[i]);
        if (send_byte(payload[i])) return -1;
    }
    if (send_byte((uint8_t)(crc >> 8))) return -1;
    int result=send_byte((uint8_t)crc);
#ifdef GFX_BATCHED
    if (GFX_ERRORS) result=-1;
#endif
#ifdef SOC_PROFILE
    gfx_profile_command_cycles += SOC_CYCLES-start;
    gfx_profile_bytes += (uint32_t)length+7u;
    ++gfx_profile_commands;
#endif
    return result;
}

int gfx_wait_frame(uint32_t frame_id) {
    for (uint32_t tries = 0; tries < 20000000u; ++tries) {
        if (GFX_ERRORS) return -1;
        if ((GFX_STATUS & GFX_FRAME_DONE) && GFX_FRAME_ID == frame_id) {
            GFX_ACK = 1u;
            return 0;
        }
    }
    return -1;
}
