#include "soc.h"
#include "gfx.h"
#include "player.h"
#include "camera.h"
#include "beacon.h"
#include "game_runtime.h"
#include "beacon_data.h"
#ifdef GAME_USE_SDRAM
#include "sdram.h"
#endif
#ifndef PLAYER_TICK_CYCLES
#define PLAYER_TICK_CYCLES 1666667u
#endif
volatile player_t game_player;
volatile beacon_state_t game_beacons;
volatile uint32_t game_frame, game_cpu_cycles;

int main(void) {
#ifdef GAME_USE_SDRAM
    uint32_t memory_test=sdram_self_test();
    if (memory_test!=0x5dad600du) { SOC_SCRATCH=memory_test; for (;;) { } }
#endif
    player_t player={0}; camera_t camera; beacon_state_t state;
    player_reset(&player,&game_world);
    camera_reset(&camera,&player,&game_camera_config,&game_camera_world);
    beacon_reset(&state,&player);
    const game_asset_set_t assets={GAME_RUNTIME_ABI,world_meshes,actor_meshes,
        GAME_WORLD_MESHES,GAME_MESH_COUNT-GAME_WORLD_MESHES,game_palette,GAME_PALETTE_COUNT};
    if (SOC_ID!=0x534f4301u || gfx_projection((int16_t)game_camera_config.focal,
        (int16_t)game_camera_config.near_z) || game_runtime_upload(&assets,0,0)) goto failed;
    game_runtime_clock_t clock; game_runtime_clock_reset(&clock,PLAYER_TICK_CYCLES);
    uint32_t frame=0, previous_win=0;
    for (;;) {
        uint32_t now=game_runtime_wait_tick(&clock), start=SOC_CYCLES;
        do {
            player_step(&player,&game_world,game_runtime_input());
            camera_step(&camera,&player,&game_camera_config,&game_camera_world);
            beacon_step(&state,&player,&game_beacon_config);
        } while (game_runtime_advance_tick(&clock,now));
        if (state.won!=previous_win) {
            if (gfx_palette(4,state.won?60:30,state.won?255:210,state.won?100:230)) goto failed;
            previous_win=state.won;
        }
        game_player.x=player.x; game_player.y=player.y; game_player.z=player.z;
        game_player.velocity_y=player.velocity_y; game_player.grounded=player.grounded;
        game_player.facing=player.facing; game_player.previous_keys=player.previous_keys;
        game_player.respawns=player.respawns;
        game_beacons.collected=state.collected; game_beacons.score=state.score;
        game_beacons.ticks=state.ticks; game_beacons.respawns=state.respawns; game_beacons.won=state.won;
        if (gfx_view_matrix(camera.view) || gfx_begin_frame(++frame)) goto failed;
        for (uint32_t h=0; h<GAME_WORLD_MESHES; ++h)
            if (gfx_draw_mesh((uint8_t)h,0,0,0)) goto failed;
        if (gfx_draw_mesh(GAME_WORLD_MESHES,(int16_t)player.x,(int16_t)player.y,(int16_t)player.z)) goto failed;
        for (uint32_t i=0; i<game_beacon_config.count; ++i)
            if (!(state.collected&(1u<<i)) && gfx_draw_mesh(GAME_WORLD_MESHES+1,
                game_beacon_positions[i][0],(int16_t)(game_beacon_positions[i][1]+64),game_beacon_positions[i][2])) goto failed;
        if (gfx_end_frame()) goto failed;
        game_cpu_cycles=SOC_CYCLES-start;
        if (game_runtime_present(frame)) goto failed;
        game_frame=frame; SOC_SCRATCH=frame;
    }
failed:
    SOC_SCRATCH=0xdead0001u; return -1;
}
