#ifndef PLAYER_H
#define PLAYER_H
#include <stdint.h>

// Reusable Q8.8 character controller. Mesh data and game settings are supplied
// by the asset profile; the controller has no Mario or renderer dependencies.
typedef struct { int16_t x, y, z; } collision_point_t;
typedef struct {
    collision_point_t a, b, c;
    int16_t min_x, max_x, min_z, max_z, slope_x, slope_z;
} collision_floor_t;
typedef struct {
    collision_point_t a, b, c;
    int16_t nx, ny, nz;
    int16_t min_x, max_x, min_y, max_y, min_z, max_z;
    uint16_t axis;
} collision_wall_t;
typedef struct {
    const collision_floor_t *floors;
    const collision_wall_t *walls;
    uint32_t floor_count, wall_count;
    int32_t spawn_x, spawn_y, spawn_z;
    int32_t speed, radius, height, step_height, gravity, jump_speed, kill_y;
} player_world_t;
typedef struct {
    int32_t x, y, z, velocity_y;
    uint32_t grounded, facing, previous_keys, respawns;
} player_t;
#define PLAYER_LEFT 1u
#define PLAYER_RIGHT 2u
#define PLAYER_FORWARD 4u
#define PLAYER_BACK 8u
#define PLAYER_JUMP 16u
// A chord uses the existing five-bit input transport without an RTL change.
#define PLAYER_RESET 15u
int32_t fixed_mul(int32_t a, int32_t b);
void player_reset(player_t *p, const player_world_t *world);
void player_step(player_t *p, const player_world_t *world, uint32_t keys);
// External game controllers can supply bounded horizontal motion while reusing
// collision and vertical integration. Split long motion and rebind queries.
void player_move_horizontal(player_t *p,const player_world_t *world,int32_t dx,int32_t dz);
void player_step_motion(player_t *p,const player_world_t *world,uint32_t keys,int32_t dx,int32_t dz);
int32_t player_floor(const player_world_t *world, int32_t x, int32_t z, int32_t ceiling);
// Optional conservative local query. NULL lists restore the legacy full scan.
// Original source-space worlds may provide plane normals for steep floors.
void player_bind_query(const player_world_t *world,const uint16_t *floors,uint32_t floor_count,
                       const uint16_t *walls,uint32_t wall_count,int32_t bound,
                       const int16_t (*floor_normals)[3]);
int32_t player_floor_index(void);
#endif
