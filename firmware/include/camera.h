#ifndef CAMERA_H
#define CAMERA_H
#include "player.h"

typedef struct {
    int32_t focus_x,focus_y,focus_z,previous_x,previous_y,previous_z,fraction;
    uint32_t initialized,respawns;
} camera_orbit_t;
typedef struct {
    int32_t distance,target_height,clearance,snap_distance;
    uint32_t follow_shift,vertical_shift,recovery_step;
} camera_orbit_config_t;

// Automatic fixed-yaw camera; all distances use the existing Q8.8 world units.
typedef struct {
    int32_t distance, min_distance, target_height;
    int32_t follow_shift, vertical_shift, air_shift;
    int32_t lookahead_ticks, lookahead_limit, look_shift;
    int32_t clearance, recovery_step, max_vertical_lag, snap_distance;
    int32_t focal, near_z;
    uint32_t pitch_count;
    int16_t pitches[4][2]; // cosine, sine; proper Y/Z view rotation
} camera_config_t;
typedef struct {
    const collision_wall_t *surfaces; // All displayed faces, including floors.
    uint32_t count;
} camera_world_t;
typedef struct {
    int32_t target_x, target_y, target_z, look_x, look_z;
    int32_t previous_x, previous_y, previous_z, fraction, pitch;
    int32_t eye_x, eye_y, eye_z;
    uint32_t respawns, obstructed;
    int16_t view[12];
} camera_t;

void camera_reset(camera_t *camera, const player_t *player,
                  const camera_config_t *config, const camera_world_t *world);
void camera_step(camera_t *camera, const player_t *player,
                 const camera_config_t *config, const camera_world_t *world);
int32_t camera_boom(const camera_world_t *world,int32_t ax,int32_t ay,int32_t az,
                    int32_t bx,int32_t by,int32_t bz,int32_t clearance);
// Caller supplies Q8 rotation rows (yaw/pitch); distances use its physics
// units. Only translation is updated, relative to player and render_scale.
void camera_orbit_step(camera_orbit_t *camera,const player_t *player,
                       const camera_orbit_config_t *config,const camera_world_t *world,
                       int16_t view[12],int32_t render_scale);
#endif
