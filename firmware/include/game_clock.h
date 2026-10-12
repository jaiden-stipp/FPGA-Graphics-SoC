#ifndef GAME_CLOCK_H
#define GAME_CLOCK_H
#include <stdint.h>
typedef struct { uint32_t previous, period, ticks; } game_runtime_clock_t;

// Call once per rendered frame. Simulation time advances only when a tick is due.
static inline int game_runtime_tick_due(game_runtime_clock_t *clock, uint32_t now) {
    clock->ticks=0;
    return (uint32_t)(now-clock->previous)>=clock->period;
}
static inline int game_clock_advance(game_runtime_clock_t *clock, uint32_t now) {
    clock->previous+=clock->period;
    ++clock->ticks;
    if (clock->ticks==4) { clock->previous=now; return 0; }
    return (uint32_t)(now-clock->previous)>=clock->period;
}
#endif
