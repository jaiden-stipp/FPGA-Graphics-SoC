#include "game_clock.h"
int due(game_runtime_clock_t*c,uint32_t n){return game_runtime_tick_due(c,n);}
int advance(game_runtime_clock_t*c,uint32_t n){return game_clock_advance(c,n);}
