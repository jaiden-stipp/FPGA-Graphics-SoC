#include "soc.h"
#include "cpu_profile.h"
#include "gfx.h"
#include "sdram.h"
#include "game_runtime.h"
#include "game_port.h"
#include "portable_data.h"
#include "render_interpolation.h"
#ifndef PLAYER_TICK_CYCLES
#define PLAYER_TICK_CYCLES 1666667u
#endif
volatile uint32_t game_frame, game_cpu_cycles,game_frame_cycles,game_present_cycles;
volatile uint32_t game_update_cycles,game_gpu_stats[13];
volatile uint32_t game_simulation_ticks,game_updates_this_frame,game_tick_wait_cycles;
volatile uint32_t game_cadence_cycles;
volatile uint32_t game_cadence_slot,game_cadence_slots[2][24];
int main(void) {
#ifdef SOC_INTEGER_MUL
    if(!(SOC_CPU_FEATURES&SOC_FEATURE_MUL)) { SOC_SCRATCH=0xdead00c2u; for(;;) {} }
#endif
#ifdef SOC_PROFILE
    if(SOC_CPU_ABI!=0x43500101u) { SOC_SCRATCH=0xdead00c1u; for(;;) {} }
#endif
    uint32_t memory_test=sdram_self_test();
    if(memory_test!=0x5dad600du) { SOC_SCRATCH=memory_test; for (;;) { } }
    if(SOC_ID!=0x534f4301u || gfx_projection(PORTABLE_FOCAL,PORTABLE_NEAR_Z) ||
       game_runtime_upload(&portable_assets,0,0) || game_port_init()) goto failed;
    game_runtime_clock_t clock;
    game_runtime_clock_reset(&clock,PLAYER_TICK_CYCLES);
    uint32_t cadence_start=clock.previous;
    uint32_t frame=0;
    for (;;) {
#ifdef SOC_PROFILE
        cpu_profile_begin(); uint32_t tick_start=SOC_CYCLES;
#endif
        uint32_t tick_begin=SOC_CYCLES;
#ifdef GAME_UNCAPPED_RENDER
        uint32_t now=SOC_CYCLES, due=game_runtime_tick_due(&clock,now);
#else
        uint32_t now=game_runtime_wait_tick(&clock), due=1;
#endif
        uint32_t start=SOC_CYCLES;
        game_tick_wait_cycles=start-tick_begin;
#ifdef SOC_PROFILE
        uint32_t tick_cycles=start-tick_start; cpu_profile_mark(0);
#endif
        game_updates_this_frame=0;
        if(due) {
            do {
                game_port_update(game_runtime_input());
                ++game_simulation_ticks; ++game_updates_this_frame;
            } while(game_runtime_advance_tick(&clock,now));
        }
        game_update_cycles=SOC_CYCLES-start;
#ifdef SOC_PROFILE
        cpu_profile_mark(1);
#endif
#ifdef GAME_RENDER_INTERPOLATION
        if(game_port_render_interpolated(++frame,game_render_fraction(&clock,SOC_CYCLES))) goto failed;
#else
        if(game_port_render(++frame)) goto failed;
#endif
        game_cpu_cycles=SOC_CYCLES-start;
#ifdef SOC_PROFILE
        cpu_profile_mark(2);
#endif
        uint32_t present_start=SOC_CYCLES;
        if(game_runtime_present(frame)) goto failed;
        game_present_cycles=SOC_CYCLES-present_start;
        game_frame_cycles=SOC_CYCLES-start;
#ifdef SOC_PROFILE
        cpu_profile_mark(3);
        cpu_profile_publish(frame,tick_cycles,game_update_cycles,game_cpu_cycles,
                            game_present_cycles,game_frame_cycles);
#endif
        for(uint32_t i=0;i<13;++i)game_gpu_stats[i]=GFX_STAT(i);
        game_frame=frame; SOC_SCRATCH=frame;
        game_cadence_cycles=SOC_CYCLES-cadence_start;
        // Publish last: loader BEGIN may halt us halfway through these writes.
        uint32_t slot=game_cadence_slot^1u;
        game_cadence_slots[slot][0]=frame;
        game_cadence_slots[slot][1]=game_simulation_ticks;
        game_cadence_slots[slot][2]=game_cadence_cycles;
        game_cadence_slots[slot][3]=game_updates_this_frame;
        game_cadence_slots[slot][4]=game_tick_wait_cycles;
        game_cadence_slots[slot][5]=game_update_cycles;
        game_cadence_slots[slot][6]=game_cpu_cycles;
        game_cadence_slots[slot][7]=game_present_cycles;
        game_cadence_slots[slot][8]=game_frame_cycles;
        game_cadence_slots[slot][9]=50000000u;
        for(uint32_t i=0;i<13;++i)game_cadence_slots[slot][10+i]=game_gpu_stats[i];
        game_cadence_slots[slot][23]=0x43540101u;
        game_cadence_slot=slot;
    }
failed:
    SOC_SCRATCH=0xdead0001u; return -1;
}
