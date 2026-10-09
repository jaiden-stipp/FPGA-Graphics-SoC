#include "soc.h"
#include "gfx_protocol.h"

int main(void) {
    // Renderer payloads are big-endian, while RV32I RAM is little-endian.
    static const uint8_t palette[] = {1, 255, 80, 32};
    static const uint8_t identity[] = {
        1,0, 0,0, 0,0, 0,0,
        0,0, 1,0, 0,0, 0,0,
        0,0, 0,0, 1,0, 0,0
    };
    static const uint8_t frame[] = {0, 0, 0, 1};
    // (-1,-1,4), (0,1,4), (1,-1,4), palette index 1; signed Q8.8.
    static const uint8_t triangle[] = {
        0xff,0, 0xff,0, 4,0,
        0,0, 1,0, 4,0,
        1,0, 0xff,0, 4,0, 1
    };
    SOC_SCRATCH = 0;
    if (SOC_ID != 0x534f4301u ||
        gfx_command(GFX_OP_SET_PALETTE, palette, sizeof palette) ||
        gfx_command(GFX_OP_SET_VIEW_MATRIX, identity, sizeof identity) ||
        gfx_command(GFX_OP_BEGIN_FRAME, frame, sizeof frame) ||
        gfx_command(GFX_OP_DRAW_TRIANGLE, triangle, sizeof triangle) ||
        gfx_command(GFX_OP_END_FRAME, 0, 0) || gfx_wait_frame(1)) {
        SOC_SCRATCH = 0xdead0001u;
        return -1;
    }
    SOC_SCRATCH = 1;
    return 0;
}
