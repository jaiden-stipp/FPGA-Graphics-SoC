#include "soc.h"
#include "gfx.h"
#include "sdram.h"
#include "game_runtime.h"
#include "game_port.h"
#include "portable_data.h"
#ifndef PLAYER_TICK_CYCLES
#define PLAYER_TICK_CYCLES 1666667u
#endif
volatile uint32_t game_frame, game_cpu_cycles,game_frame_cycles,game_present_cycles;
volatile uint32_t game_update_cycles,game_gpu_stats[13];
int main(void) {
    uint32_t memory_test=sdram_self_test();
    if(memory_test!=0x5dad600du) { SOC_SCRATCH=memory_test; for (;;) { } }
    if(SOC_ID!=0x534f4301u || gfx_projection(PORTABLE_FOCAL,PORTABLE_NEAR_Z) ||
       game_runtime_upload(&portable_assets,0,0) || game_port_init()) goto failed;
    game_runtime_clock_t clock;
    game_runtime_clock_reset(&clock,PLAYER_TICK_CYCLES);
    uint32_t frame=0;
    for (;;) {
        uint32_t now=game_runtime_wait_tick(&clock), start=SOC_CYCLES;
        do { game_port_update(game_runtime_input()); }
        while(game_runtime_advance_tick(&clock,now));
        game_update_cycles=SOC_CYCLES-start;
        if(game_port_render(++frame)) goto failed;
        game_cpu_cycles=SOC_CYCLES-start;
        uint32_t present_start=SOC_CYCLES;
        if(game_runtime_present(frame)) goto failed;
        game_present_cycles=SOC_CYCLES-present_start;
        game_frame_cycles=SOC_CYCLES-start;
        for(uint32_t i=0;i<13;++i)game_gpu_stats[i]=GFX_STAT(i);
        game_frame=frame; SOC_SCRATCH=frame;
    }
failed:
    SOC_SCRATCH=0xdead0001u; return -1;
}
