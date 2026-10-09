#ifndef FIRST_PERSON_H
#define FIRST_PERSON_H
#include "player.h"
typedef struct {
    const int16_t (*rotations)[2]; // 64 [cos,sin] Q8.8 pairs
    uint32_t initial_yaw;
    int32_t eye_height, region_radius;
} first_person_config_t;
typedef struct { uint32_t yaw, respawns; int16_t view[12]; } first_person_t;
void first_person_reset(first_person_t *camera, const player_t *player, const first_person_config_t *config);
void first_person_step(first_person_t *camera, player_t *player, const player_world_t *world,
                       const first_person_config_t *config, uint32_t keys);
#endif
