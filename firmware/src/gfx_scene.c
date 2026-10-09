#include "soc.h"
#include "gfx.h"
#include "gfx_protocol.h"

static void be16(uint8_t *out, uint16_t v) {
    out[0] = (uint8_t)(v >> 8); out[1] = (uint8_t)v;
}
int gfx_view_matrix(const int16_t matrix[12]) {
    uint8_t payload[24];
    for (uint32_t i = 0; i < 12; ++i) be16(payload + 2*i, (uint16_t)matrix[i]);
    return gfx_command(GFX_OP_SET_VIEW_MATRIX, payload, sizeof payload);
}
int gfx_projection(int16_t focal, int16_t near_z) {
    uint8_t payload[10];
    be16(payload, (uint16_t)focal); be16(payload + 2, (uint16_t)focal);
    be16(payload + 4, 160); be16(payload + 6, 120);
    be16(payload + 8, (uint16_t)near_z);
    return gfx_command(GFX_OP_SET_PROJECTION, payload, sizeof payload);
}
int gfx_palette(uint8_t index, uint8_t r, uint8_t g, uint8_t b) {
    uint8_t payload[4] = {index, r, g, b};
    return gfx_command(GFX_OP_SET_PALETTE, payload, sizeof payload);
}
int gfx_identity_view(void) {
    static const uint8_t identity[24] = {
        1,0, 0,0, 0,0, 0,0,
        0,0, 1,0, 0,0, 0,0,
        0,0, 0,0, 1,0, 0,0
    };
    return gfx_command(GFX_OP_SET_VIEW_MATRIX, identity, sizeof identity);
}
int gfx_begin_frame(uint32_t id) {
    uint8_t payload[4] = {(uint8_t)(id >> 24), (uint8_t)(id >> 16),
                          (uint8_t)(id >> 8), (uint8_t)id};
    return gfx_command(GFX_OP_BEGIN_FRAME, payload, sizeof payload);
}
int gfx_end_frame(void) { return gfx_command(GFX_OP_END_FRAME, 0, 0); }
int gfx_define_mesh(uint8_t handle, uint16_t vertices, uint16_t triangles) {
    uint8_t payload[5] = {handle, 0, 0, 0, 0};
    be16(payload + 1, vertices); be16(payload + 3, triangles);
    return gfx_command(GFX_OP_DEFINE_MESH, payload, sizeof payload);
}
int gfx_vertex(uint8_t handle, uint8_t index, int16_t x, int16_t y, int16_t z) {
    uint8_t payload[8] = {handle, index, 0, 0, 0, 0, 0, 0};
    be16(payload + 2, (uint16_t)x); be16(payload + 4, (uint16_t)y);
    be16(payload + 6, (uint16_t)z);
    return gfx_command(GFX_OP_UPLOAD_VERTEX, payload, sizeof payload);
}
int gfx_index(uint8_t handle, uint16_t index, uint8_t a, uint8_t b,
              uint8_t c, uint8_t color) {
    uint8_t payload[7] = {handle, 0, 0, a, b, c, color};
    be16(payload + 1, index);
    return gfx_command(GFX_OP_UPLOAD_INDEX, payload, sizeof payload);
}
int gfx_draw_mesh(uint8_t handle, int16_t x, int16_t y, int16_t z) {
    uint8_t payload[25] = {
        handle,
        1,0, 0,0, 0,0, 0,0,
        0,0, 1,0, 0,0, 0,0,
        0,0, 0,0, 1,0, 0,0
    };
    be16(payload + 7, (uint16_t)x);
    be16(payload + 15, (uint16_t)y);
    be16(payload + 23, (uint16_t)z);
    return gfx_command(GFX_OP_DRAW_MESH, payload, sizeof payload);
}
int gfx_draw_matrix(uint8_t handle, const int16_t matrix[12]) {
    uint8_t payload[25];
    payload[0] = handle;
    for (uint32_t i=0; i<12; ++i) be16(payload+1+2*i,(uint16_t)matrix[i]);
    return gfx_command(GFX_OP_DRAW_MESH,payload,sizeof payload);
}
