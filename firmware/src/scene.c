// A small static 3D scene. CPU controls camera; GPU transforms and draws every mesh.
#include "soc.h"
#include "gfx.h"
#include "scene_data.h"

#ifndef SCENE_TICK_CYCLES
#define SCENE_TICK_CYCLES 1666667u
#endif

volatile uint32_t scene_angle, scene_distance, scene_frame;

int main(void) {
    uint32_t frame = 0, angle = 0;
    int16_t distance = 3072;
    SOC_SCRATCH = 0;
    if (SOC_ID != 0x534f4301u || gfx_projection(256, 512)) goto failed;
    for (uint32_t i = 0; i < SCENE_PALETTE_COUNT; ++i)
        if (gfx_palette((uint8_t)i, scene_palette[i][0], scene_palette[i][1], scene_palette[i][2])) goto failed;
    for (uint32_t h = 0; h < SCENE_MESH_COUNT; ++h) {
        const scene_mesh_t *mesh = scene_meshes + h;
        if (gfx_define_mesh((uint8_t)h, mesh->vertex_count, mesh->triangle_count)) goto failed;
        for (uint32_t i = 0; i < mesh->vertex_count; ++i) {
            const scene_vertex_t *v = mesh->vertices + i;
            if (gfx_vertex((uint8_t)h, (uint8_t)i, v->x, v->y, v->z)) goto failed;
        }
        for (uint32_t i = 0; i < mesh->triangle_count; ++i) {
            const scene_triangle_t *t = mesh->triangles + i;
            if (gfx_index((uint8_t)h, (uint16_t)i, t->a, t->b, t->c, t->color)) goto failed;
        }
    }
    uint32_t previous = SOC_CYCLES;
    for (;;) {
        uint32_t now;
        do { now = SOC_CYCLES; } while ((uint32_t)(now - previous) < SCENE_TICK_CYCLES);
        previous = now;
        uint32_t keys = SOC_BUTTONS;
        if ((keys & 3u) == BUTTON_LEFT) angle = (angle + 31u) & 31u;
        if ((keys & 3u) == BUTTON_RIGHT) angle = (angle + 1u) & 31u;
        if ((keys & (BUTTON_FORWARD | BUTTON_BACK)) == BUTTON_FORWARD && distance > 2560) distance -= 64;
        if ((keys & (BUTTON_FORWARD | BUTTON_BACK)) == BUTTON_BACK && distance < 4608) distance += 64;
        if (keys & BUTTON_RESET_VIEW) { angle = 0; distance = 3072; }
        int16_t view[12];
        for (uint32_t i = 0; i < 12; ++i) view[i] = scene_camera[angle][i];
        view[11] = distance;
        scene_angle = angle; scene_distance = (uint32_t)distance;
        // Camera/projection state may change only between GPU frames.
        if (gfx_view_matrix(view) || gfx_begin_frame(++frame)) goto failed;
        for (uint32_t h = 0; h < SCENE_MESH_COUNT; ++h)
            if (gfx_draw_mesh((uint8_t)h, 0, 0, 0)) goto failed;
        if (gfx_end_frame() || gfx_wait_frame(frame)) goto failed;
        scene_frame = frame; SOC_SCRATCH = frame;
    }
failed:
    SOC_SCRATCH = 0xdead0001u;
    return -1;
}
