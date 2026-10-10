#ifndef CPU_PROFILE_H
#define CPU_PROFILE_H
#include "soc.h"
#ifdef SOC_PROFILE_FINE
#ifndef SOC_PROFILE_DETAIL
#error SOC_PROFILE_FINE requires SOC_PROFILE_DETAIL
#endif
#define CPU_FINE_SCOPES 7u
#define CPU_FINE_EVENTS 6u
#define CPU_FINE_WORDS 22u
enum { PROFILE_CRC, PROFILE_TX_CHECK, PROFILE_TX_WRITE, PROFILE_FRACTION,
       PROFILE_INTERSECTION, PROFILE_ADMISSION, PROFILE_UPLOAD };
enum { EVENT_GPU_ADMITTED, EVENT_GPU_DRAW, EVENT_DIRECT_DRAW, EVENT_UPLOAD,
       EVENT_CLIP_ACCEPT, EVENT_CLIP_REJECT };
extern volatile uint32_t game_fine_slots[2][CPU_FINE_WORDS];
void cpu_fine_end(uint32_t scope,uint32_t start);
void cpu_fine_event(uint32_t event);
#define FINE_START(name) uint32_t name=SOC_CYCLES
#define FINE_END(scope,name) cpu_fine_end(scope,name)
#define FINE_EVENT(event) cpu_fine_event(event)
#else
#define FINE_START(name)
#define FINE_END(scope,name)
#define FINE_EVENT(event)
#endif
#ifdef SOC_PROFILE_DETAIL
#ifndef SOC_PROFILE
#error SOC_PROFILE_DETAIL requires SOC_PROFILE
#endif
// Separate optional ABI, committed with the original completed-frame slot.
// Each scope stores elapsed cycles and invocation count. Timers are inclusive.
#define CPU_DETAIL_SCOPES 7u
#define CPU_DETAIL_WORDS 16u
enum { PROFILE_VISIBILITY, PROFILE_VERTICES, PROFILE_CLIPPING,
       PROFILE_ANIMATION_STEP, PROFILE_JOINTS, PROFILE_SKIN, PROFILE_CAMERA };
extern volatile uint32_t game_detail_slots[2][CPU_DETAIL_WORDS];
void cpu_detail_end(uint32_t scope,uint32_t start);
#define DETAIL_START(name) uint32_t name=SOC_CYCLES
#define DETAIL_END(scope,name) cpu_detail_end(scope,name)
#else
#define DETAIL_START(name)
#define DETAIL_END(scope,name)
#endif
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
