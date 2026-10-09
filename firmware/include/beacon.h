#ifndef BEACON_H
#define BEACON_H
#include "player.h"
typedef struct {
    const int16_t (*positions)[3];
    uint32_t count;
    int32_t radius, height;
} beacon_config_t;
typedef struct { uint32_t collected, score, ticks, respawns, won; } beacon_state_t;
void beacon_reset(beacon_state_t *state, const player_t *player);
void beacon_step(beacon_state_t *state, const player_t *player, const beacon_config_t *config);
#endif
