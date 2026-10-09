// Profile-driven CPU gameplay; all triangles use the existing hardware GPU.
#include "soc.h"
#include "gfx.h"
#include "player.h"
#include "camera.h"
#include "game_runtime.h"
#include "game_data.h"
#ifdef GAME_USE_SDRAM
#include "sdram.h"
#endif
#ifndef PLAYER_TICK_CYCLES
#define PLAYER_TICK_CYCLES 1666667u
#endif

volatile player_t game_player;
volatile uint32_t game_frame;
volatile uint32_t game_animation_clip,game_animation_frame;
volatile uint32_t game_animation_cycles,game_upload_cycles,game_cpu_cycles;
#ifdef GAME_HAS_ANIMATION
static animation_matrix_t animation_matrices[GAME_ANIMATION_JOINTS];
static scene_vertex_t animation_vertices[GAME_ANIMATION_VERTICES];
#endif

static const scene_mesh_t *mesh_at(uint32_t h) {
    return h<GAME_WORLD_MESHES ? world_meshes+h : actor_meshes+(h-GAME_WORLD_MESHES);
}
int main(void) {
#ifdef GAME_USE_SDRAM
    uint32_t memory_test=sdram_self_test();
    if (memory_test!=0x5dad600du) { SOC_SCRATCH=memory_test; for (;;) { } }
#endif
    player_t player={0};
    camera_t camera;
#ifdef GAME_HAS_ANIMATION
    animation_t animation;
#endif
    uint32_t frame=0;
    SOC_SCRATCH=0;
    player_reset(&player,&game_world);
#ifdef PLAYER_VALIDATION_VIEW
    // Simulation-only fixed camera fixture; omitted from the board firmware.
    player.x=game_validation_positions[PLAYER_VALIDATION_VIEW][0];
    player.y=game_validation_positions[PLAYER_VALIDATION_VIEW][1];
    player.z=game_validation_positions[PLAYER_VALIDATION_VIEW][2];
#endif
    camera_reset(&camera,&player,&game_camera_config,&game_camera_world);
#ifdef GAME_HAS_ANIMATION
    animation_reset(&animation,&player,&game_animation_package);
    animation_pose(&animation,&game_animation_package,animation_matrices,animation_vertices);
#endif
    if (SOC_ID!=0x534f4301u || gfx_projection((int16_t)game_camera_config.focal,(int16_t)game_camera_config.near_z)) goto failed;
    const game_asset_set_t assets={GAME_RUNTIME_ABI,world_meshes,actor_meshes,
        GAME_WORLD_MESHES,GAME_MESH_COUNT-GAME_WORLD_MESHES,game_palette,GAME_PALETTE_COUNT};
#ifdef GAME_HAS_ANIMATION
    if (game_runtime_upload(&assets,animation_vertices,GAME_ANIMATION_VERTICES)) goto failed;
#else
    if (game_runtime_upload(&assets,0,0)) goto failed;
#endif
    game_runtime_clock_t clock;
    game_runtime_clock_reset(&clock,PLAYER_TICK_CYCLES);
    for (;;) {
        // Fixed 30 Hz simulation, with bounded catch-up after a slow GPU frame.
        uint32_t now=game_runtime_wait_tick(&clock);
        uint32_t work_start=SOC_CYCLES;
        do {
            player_step(&player,&game_world,game_runtime_input());
            camera_step(&camera,&player,&game_camera_config,&game_camera_world);
#ifdef GAME_HAS_ANIMATION
            animation_step(&animation,&player,&game_animation_package);
#endif
        } while (game_runtime_advance_tick(&clock,now));
#ifdef GAME_HAS_ANIMATION
        uint32_t animation_start=SOC_CYCLES;
        animation_pose(&animation,&game_animation_package,animation_matrices,animation_vertices);
        game_animation_cycles=SOC_CYCLES-animation_start;
        game_animation_clip=animation.clip; game_animation_frame=animation.phase>>8;
        uint32_t upload_start=SOC_CYCLES, actor_vertex=0;
        for (uint32_t h=GAME_WORLD_MESHES;h<GAME_MESH_COUNT;++h)
            for (uint32_t i=0;i<mesh_at(h)->vertex_count;++i) {
                const scene_vertex_t *v=animation_vertices+actor_vertex++;
                if (gfx_vertex((uint8_t)h,(uint8_t)i,v->x,v->y,v->z)) goto failed;
            }
        game_upload_cycles=SOC_CYCLES-upload_start;
#endif
        int16_t model[12];
        for (uint32_t i=0; i<12; ++i) model[i]=game_facing[player.facing][i];
        model[3]=(int16_t)player.x; model[7]=(int16_t)player.y; model[11]=(int16_t)player.z;
        game_player.x=player.x; game_player.y=player.y; game_player.z=player.z;
        game_player.velocity_y=player.velocity_y; game_player.grounded=player.grounded;
        game_player.facing=player.facing; game_player.previous_keys=player.previous_keys;
        game_player.respawns=player.respawns;
        if (gfx_view_matrix(camera.view) || gfx_begin_frame(++frame)) goto failed;
        for (uint32_t h=0; h<GAME_MESH_COUNT; ++h) {
            if (h<GAME_WORLD_MESHES) { if (gfx_draw_mesh((uint8_t)h,0,0,0)) goto failed; }
            else if (gfx_draw_matrix((uint8_t)h,model)) goto failed;
        }
        if (gfx_end_frame()) goto failed;
        game_cpu_cycles=SOC_CYCLES-work_start;
        if (game_runtime_present(frame)) goto failed;
        game_frame=frame; SOC_SCRATCH=frame;
    }
failed:
    SOC_SCRATCH=0xdead0001u;
    return -1;
}
