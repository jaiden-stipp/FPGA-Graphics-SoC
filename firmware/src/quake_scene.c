#include "soc.h"
#include "gfx.h"
#include "player.h"
#include "first_person.h"
#include "game_runtime.h"
#include "quake_data.h"
#ifdef GAME_USE_SDRAM
#include "sdram.h"
#endif
#ifndef PLAYER_TICK_CYCLES
#define PLAYER_TICK_CYCLES 1666667u
#endif
volatile player_t game_player;
volatile uint32_t game_frame, game_cpu_cycles;
int main(void) {
#ifdef GAME_USE_SDRAM
    uint32_t memory_test=sdram_self_test();
    if(memory_test!=0x5dad600du) { SOC_SCRATCH=memory_test; for (;;) { } }
#endif
    player_t player={0}; first_person_t camera;
    player_reset(&player,&game_world); first_person_reset(&camera,&player,&game_first_person);
    const game_asset_set_t assets={GAME_RUNTIME_ABI,world_meshes,0,GAME_WORLD_MESHES,0,game_palette,GAME_PALETTE_COUNT};
    if(SOC_ID!=0x534f4301u || gfx_projection(GAME_FOCAL,GAME_NEAR_Z) || game_runtime_upload(&assets,0,0)) goto failed;
    game_runtime_clock_t clock; game_runtime_clock_reset(&clock,PLAYER_TICK_CYCLES);
    uint32_t frame=0;
    for (;;) {
        uint32_t now=game_runtime_wait_tick(&clock), start=SOC_CYCLES;
        do { first_person_step(&camera,&player,&game_world,&game_first_person,game_runtime_input()); }
        while(game_runtime_advance_tick(&clock,now));
        game_player.x=player.x; game_player.y=player.y; game_player.z=player.z;
        game_player.velocity_y=player.velocity_y; game_player.grounded=player.grounded;
        game_player.facing=player.facing; game_player.previous_keys=player.previous_keys; game_player.respawns=player.respawns;
        if(gfx_view_matrix(camera.view) || gfx_begin_frame(++frame)) goto failed;
        for(uint32_t h=0;h<GAME_WORLD_MESHES;++h) if(gfx_draw_mesh((uint8_t)h,0,0,0)) goto failed;
        if(gfx_end_frame()) goto failed;
        game_cpu_cycles=SOC_CYCLES-start;
        if(game_runtime_present(frame)) goto failed;
        game_frame=frame; SOC_SCRATCH=frame;
    }
failed:
    SOC_SCRATCH=0xdead0001u; return -1;
}
