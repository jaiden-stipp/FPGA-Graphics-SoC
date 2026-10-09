// Catch: CPU owns input, movement, collision, score and the game loop.
// GPU owns mesh transforms, clipping, rasterization, depth and frame presentation.
#include "soc.h"
#include "gfx.h"

#ifndef GAME_TICK_CYCLES
#define GAME_TICK_CYCLES 1666667u /* 30 Hz at 50 MHz; change for another clock. */
#endif

volatile uint32_t game_score, game_misses;

static int rectangle(uint8_t handle, int16_t half_x, int16_t half_y, uint8_t color) {
    return gfx_define_mesh(handle, 4, 2) ||
        gfx_vertex(handle, 0, -half_x, -half_y, 0) ||
        gfx_vertex(handle, 1, -half_x, half_y, 0) ||
        gfx_vertex(handle, 2, half_x, half_y, 0) ||
        gfx_vertex(handle, 3, half_x, -half_y, 0) ||
        gfx_index(handle, 0, 0, 1, 2, color) ||
        gfx_index(handle, 1, 0, 2, 3, color);
}

int main(void) {
    int16_t paddle_x = 0, block_x = -160, block_y = 240;
    uint32_t frame = 0, score = 0, misses = 0;
    SOC_SCRATCH = 0;
    if (SOC_ID != 0x534f4301u || SOC_CLOCK_HZ != 50000000u ||
        gfx_identity_view() || gfx_palette(1, 40, 160, 255) ||
        gfx_palette(2, 255, 180, 40) ||
        rectangle(0, 64, 16, 1) || rectangle(1, 24, 24, 2)) goto failed;

    uint32_t previous_tick = SOC_CYCLES;
    for (;;) {
        uint32_t now;
        do { now = SOC_CYCLES; } while ((uint32_t)(now - previous_tick) < GAME_TICK_CYCLES);
        // At most one update per displayed frame; no unbounded catch-up after a slow render.
        previous_tick = now;
        uint32_t buttons = SOC_BUTTONS;
        if ((buttons & (BUTTON_LEFT | BUTTON_RIGHT)) == BUTTON_LEFT) paddle_x -= 32;
        if ((buttons & (BUTTON_LEFT | BUTTON_RIGHT)) == BUTTON_RIGHT) paddle_x += 32;
        if (paddle_x < -320) paddle_x = -320;
        if (paddle_x > 320) paddle_x = 320;
        block_y -= 16;
        if (block_y <= -200) {
            int32_t distance = (int32_t)block_x - paddle_x;
            if (distance >= -88 && distance <= 88) ++score;
            else ++misses;
            // Feedback: green after a catch, red after a miss.
            if (gfx_palette(2, distance >= -88 && distance <= 88 ? 40 : 255,
                            distance >= -88 && distance <= 88 ? 255 : 40, 40)) goto failed;
            block_y = 240;
            block_x = block_x >= 160 ? -160 : block_x + 80;
        }
        // Keep inspectable game state in CPU RAM for debugging and later HUD work.
        game_score = score; game_misses = misses;
        ++frame;
        if (gfx_begin_frame(frame) ||
            gfx_draw_mesh(0, paddle_x, -240, 1024) ||
            gfx_draw_mesh(1, block_x, block_y, 1024) ||
            gfx_end_frame() || gfx_wait_frame(frame)) goto failed;
        SOC_SCRATCH = frame;
    }
failed:
    SOC_SCRATCH = 0xdead0001u;
    return -1;
}
