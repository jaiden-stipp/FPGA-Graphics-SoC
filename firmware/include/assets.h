#ifndef ASSETS_H
#define ASSETS_H
#include <stdint.h>
// Common fixed-point mesh ABI shared by scene viewers and game applications.
typedef struct { int16_t x, y, z; } scene_vertex_t;
typedef struct { uint8_t a, b, c, color; } scene_triangle_t;
typedef struct {
    const scene_vertex_t *vertices;
    const scene_triangle_t *triangles;
    uint16_t vertex_count, triangle_count;
} scene_mesh_t;
#endif
