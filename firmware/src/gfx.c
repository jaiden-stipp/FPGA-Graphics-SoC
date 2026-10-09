#include "soc.h"
#include "gfx_protocol.h"

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

static int send_byte(uint8_t byte) {
    for (uint32_t tries = 0; tries < 20000000u; ++tries) {
        if (GFX_ERRORS) return -1;
        if (GFX_STATUS & GFX_TX_READY) { GFX_DATA = byte; return 0; }
    }
    return -1;
}

int gfx_command(uint8_t opcode, const uint8_t *payload, uint8_t length) {
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
    return send_byte((uint8_t)crc);
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
