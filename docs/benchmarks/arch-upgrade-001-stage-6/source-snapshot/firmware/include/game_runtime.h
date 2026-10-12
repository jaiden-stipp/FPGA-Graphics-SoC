#ifndef GAME_RUNTIME_H
#define GAME_RUNTIME_H
#include "assets.h"
#include "game_clock.h"
#define GAME_RUNTIME_ABI 1u

// Immutable package descriptors; executable modules call this direct-call ABI.
typedef struct {
    uint32_t abi_version;
    const scene_mesh_t *world_meshes, *actor_meshes;
    uint32_t world_count, actor_count;
    const uint8_t (*palette)[3];
    uint32_t palette_count;
} game_asset_set_t;

int game_runtime_upload(const game_asset_set_t *assets,
                        const scene_vertex_t *posed_vertices, uint32_t posed_count);
void game_runtime_clock_reset(game_runtime_clock_t *clock, uint32_t period);
uint32_t game_runtime_wait_tick(game_runtime_clock_t *clock);
int game_runtime_advance_tick(game_runtime_clock_t *clock, uint32_t now);
uint32_t game_runtime_input(void);
int game_runtime_present(uint32_t frame);
#endif
