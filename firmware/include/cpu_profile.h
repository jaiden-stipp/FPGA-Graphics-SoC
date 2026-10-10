#ifndef CPU_PROFILE_H
#define CPU_PROFILE_H
#include "soc.h"
#ifdef SOC_PROFILE
// Fixed ABI: 4 phase records (cycles,retired,freezes,bubbles,redirects,status,full).
// Then command cycles,FIFO wait span,bytes,commands,tick wall,update wall,
// CPU wall,present wall,frame wall,frame ID,clock,ABI. 53 words per slot; followed by the 13 completed GPU counters.
#define CPU_PROFILE_WORDS 53u
extern volatile uint32_t gfx_profile_command_cycles, gfx_profile_fifo_cycles;
extern volatile uint32_t gfx_profile_bytes, gfx_profile_commands;
extern volatile uint32_t game_profile_slots[2][CPU_PROFILE_WORDS];
extern volatile uint32_t game_profile_slot;
void cpu_profile_begin(void);
void cpu_profile_mark(uint32_t phase);
void cpu_profile_publish(uint32_t frame, uint32_t tick, uint32_t update,
                         uint32_t cpu, uint32_t present, uint32_t total);
#endif
#endif
