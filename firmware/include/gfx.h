#ifndef GFX_H
#define GFX_H
#include <stdint.h>
int gfx_palette(uint8_t index, uint8_t r, uint8_t g, uint8_t b);
int gfx_identity_view(void);
int gfx_view_matrix(const int16_t matrix[12]);
int gfx_projection(int16_t focal, int16_t near_z);
int gfx_begin_frame(uint32_t id);
int gfx_end_frame(void);
int gfx_define_mesh(uint8_t handle, uint16_t vertices, uint16_t triangles);
int gfx_vertex(uint8_t handle, uint8_t index, int16_t x, int16_t y, int16_t z);
int gfx_index(uint8_t handle, uint16_t index, uint8_t a, uint8_t b,
              uint8_t c, uint8_t color);
int gfx_draw_mesh(uint8_t handle, int16_t x, int16_t y, int16_t z);
int gfx_draw_matrix(uint8_t handle, const int16_t matrix[12]);
#endif
