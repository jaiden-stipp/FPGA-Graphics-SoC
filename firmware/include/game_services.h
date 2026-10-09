#ifndef GAME_SERVICES_H
#define GAME_SERVICES_H
#include "player.h"
#include "assets.h"
typedef struct { uint32_t buttons,yaw,has_look; int32_t pitch; } game_input_t;
typedef struct { int16_t min_x,max_x,min_y,max_y,min_z,max_z; } game_bounds_t;
typedef struct {
    game_bounds_t local;
    int32_t x,y,z,phase;
    uint32_t enabled,frame;
} game_object_t;
typedef struct { uint32_t yaw; int32_t pitch; int16_t view[12]; } game_view_t;
#define GAME_FIRE 32u
#define GAME_USE 64u
#define GAME_RESET 128u
void game_input_decode(game_input_t *input,uint32_t word);
uint32_t game_movement_keys(const game_input_t *input,uint32_t yaw);
void game_view_update(game_view_t *view,const player_t *player,int32_t eye,const int16_t rotations[256][2]);
int game_object_overlap(const game_object_t *object,const player_t *player,int32_t radius,int32_t height);
void game_door_step(game_object_t *door,int opening,int32_t speed,int32_t travel);
int game_pickup_step(game_object_t *pickup,const player_t *player,int32_t radius,int32_t height);
uint32_t game_animation_frame(uint32_t tick,uint32_t period,uint32_t count);
int game_mesh_frame(uint8_t handle,const scene_vertex_t *vertices,uint32_t count);
int game_hud_begin(const game_view_t *view,const player_t *player,int32_t eye,uint32_t focal);
int game_hud_rect(int16_t x,int16_t y,int16_t width,int16_t height,uint8_t color);
int game_hud_number(int16_t x,int16_t y,uint32_t value,uint32_t digits,uint8_t color);
#endif
