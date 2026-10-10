#include "cpu_profile.h"
#ifdef SOC_PROFILE
volatile uint32_t game_profile_slots[2][CPU_PROFILE_WORDS];
volatile uint32_t game_profile_slot;
static uint32_t previous[7], records[28], gpu_start[4];
static void snapshot(uint32_t *v) {
    SOC_CPU_SNAPSHOT=1u;
    v[0]=SOC_CPU_CYCLES; v[1]=SOC_CPU_RETIRED; v[2]=SOC_CPU_FREEZES;
    v[3]=SOC_CPU_BUBBLES; v[4]=SOC_CPU_REDIRECTS;
    v[5]=SOC_GPU_STATUS_READS; v[6]=SOC_GPU_FULL_READS;
}
void cpu_profile_begin(void) {
    gpu_start[0]=gfx_profile_command_cycles; gpu_start[1]=gfx_profile_fifo_cycles;
    gpu_start[2]=gfx_profile_bytes; gpu_start[3]=gfx_profile_commands;
    snapshot(previous);
}
void cpu_profile_mark(uint32_t phase) {
    uint32_t current[7]; snapshot(current);
    for (uint32_t i=0;i<7u;++i) {
        records[phase*7u+i]=current[i]-previous[i]; previous[i]=current[i];
    }
}
void cpu_profile_publish(uint32_t frame, uint32_t tick, uint32_t update,
                         uint32_t cpu, uint32_t present, uint32_t total) {
    uint32_t slot=game_profile_slot^1u;
    for(uint32_t i=0;i<28u;++i)game_profile_slots[slot][i]=records[i];
    game_profile_slots[slot][28]=gfx_profile_command_cycles-gpu_start[0];
    game_profile_slots[slot][29]=gfx_profile_fifo_cycles-gpu_start[1];
    game_profile_slots[slot][30]=gfx_profile_bytes-gpu_start[2];
    game_profile_slots[slot][31]=gfx_profile_commands-gpu_start[3];
    game_profile_slots[slot][32]=tick; game_profile_slots[slot][33]=update;
    game_profile_slots[slot][34]=cpu; game_profile_slots[slot][35]=present;
    game_profile_slots[slot][36]=total; game_profile_slots[slot][37]=frame;
    game_profile_slots[slot][38]=SOC_CLOCK_HZ; game_profile_slots[slot][39]=SOC_CPU_ABI;
    for(uint32_t i=0;i<13u;++i)game_profile_slots[slot][40u+i]=GFX_STAT(i);
    // Commit last: interrupted next-frame publication cannot corrupt this slot.
    game_profile_slot=slot;
}
#endif
