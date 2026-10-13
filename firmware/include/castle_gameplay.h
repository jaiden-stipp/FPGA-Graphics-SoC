#ifndef CASTLE_GAMEPLAY_H
#define CASTLE_GAMEPLAY_H
#include "world.h"
#include "game_services.h"
enum { CASTLE_ACTION_IDLE,CASTLE_ACTION_WALK,CASTLE_ACTION_AIR,
       CASTLE_ACTION_SLIDE,CASTLE_ACTION_GROUND_POUND };
typedef struct {
    int32_t speed,vx,vz,remainder_x,remainder_z;
    uint32_t action,yaw,previous_buttons;
} castle_controller_t;
void castle_controller_reset(castle_controller_t *state,const player_t *player);
void castle_controller_step(castle_controller_t *state,player_t *player,
                            const world_area_t *area,uint32_t slide_terrain,uint32_t keys,uint32_t buttons,uint32_t intended_yaw);
void castle_gameplay_init(void);
void castle_gameplay_enter(uint32_t area);
uint32_t castle_gameplay_step(player_t *player,uint32_t area,uint32_t buttons,uint32_t action);
uint32_t castle_gameplay_stars(void);
uint32_t castle_gameplay_keys(void);
uint32_t castle_gameplay_frozen(void);
uint32_t castle_gameplay_mission(void);
int32_t castle_gameplay_probe(uint32_t field);
int castle_gameplay_draw(uint32_t area,const player_t *player,const game_view_t *view);
#endif
