#include "soc.h"
#include "gfx.h"
#include "game_runtime.h"

int game_runtime_upload(const game_asset_set_t *a,
                        const scene_vertex_t *posed, uint32_t posed_count) {
    if (a->abi_version!=GAME_RUNTIME_ABI || a->world_count>16u ||
        a->actor_count>16u-a->world_count || !a->palette_count || a->palette_count>256u)
        return -1;
    uint32_t actor_vertices=0;
    // Validate the complete descriptor before emitting any graphics commands.
    for (uint32_t h=0; h<a->world_count+a->actor_count; ++h) {
        const scene_mesh_t *m=h<a->world_count ? a->world_meshes+h : a->actor_meshes+h-a->world_count;
        if (!m->vertex_count || m->vertex_count>128 || !m->triangle_count || m->triangle_count>256) return -1;
        if (h>=a->world_count) actor_vertices+=m->vertex_count;
        for (uint32_t i=0; i<m->triangle_count; ++i) {
            const scene_triangle_t *t=m->triangles+i;
            if (t->a>=m->vertex_count || t->b>=m->vertex_count ||
                t->c>=m->vertex_count || t->color>=a->palette_count) return -1;
        }
    }
    if ((posed && posed_count!=actor_vertices) || (!posed && posed_count)) return -1;
    for (uint32_t i=0; i<a->palette_count; ++i)
        if (gfx_palette((uint8_t)i,a->palette[i][0],a->palette[i][1],a->palette[i][2])) return -1;
    uint32_t actor_vertex=0;
    for (uint32_t h=0; h<a->world_count+a->actor_count; ++h) {
        const scene_mesh_t *m=h<a->world_count ? a->world_meshes+h : a->actor_meshes+h-a->world_count;
        if (gfx_define_mesh((uint8_t)h,m->vertex_count,m->triangle_count)) return -1;
        for (uint32_t i=0; i<m->vertex_count; ++i) {
            const scene_vertex_t *v=posed && h>=a->world_count ? posed+actor_vertex++ : m->vertices+i;
            if (gfx_vertex((uint8_t)h,(uint8_t)i,v->x,v->y,v->z)) return -1;
        }
        for (uint32_t i=0; i<m->triangle_count; ++i) {
            const scene_triangle_t *t=m->triangles+i;
            if (gfx_index((uint8_t)h,(uint16_t)i,t->a,t->b,t->c,t->color)) return -1;
        }
    }
    return 0;
}
void game_runtime_clock_reset(game_runtime_clock_t *clock, uint32_t period) {
    clock->previous=SOC_CYCLES; clock->period=period; clock->ticks=0;
}
uint32_t game_runtime_wait_tick(game_runtime_clock_t *clock) {
    uint32_t now=SOC_CYCLES;
    while ((uint32_t)(now-clock->previous)<clock->period) now=SOC_CYCLES;
    clock->ticks=0;
    return now;
}
int game_runtime_advance_tick(game_runtime_clock_t *clock, uint32_t now) {
    clock->previous+=clock->period;
    ++clock->ticks;
    if (clock->ticks==4) { clock->previous=now; return 0; }
    return (uint32_t)(now-clock->previous)>=clock->period;
}
uint32_t game_runtime_input(void) { return SOC_BUTTONS; }
int game_runtime_present(uint32_t frame) { return gfx_wait_frame(frame); }
