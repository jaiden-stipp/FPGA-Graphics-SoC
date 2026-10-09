#ifndef ANIMATION_H
#define ANIMATION_H
#include "assets.h"
#include "player.h"
enum { ANIMATION_IDLE=0, ANIMATION_WALK=1, ANIMATION_JUMP=2, ANIMATION_LAND=3 };
typedef struct { int16_t parent,x,y,z; } animation_joint_t;
typedef struct { uint16_t count,index; } animation_channel_t;
typedef struct {
    const animation_channel_t *channels;
    uint16_t flags,start,end,loop;
} animation_clip_t;
typedef struct {
    const animation_joint_t *joints;
    const animation_clip_t *clips;
    const int16_t *values,*sines;
    const scene_mesh_t *meshes;
    const uint8_t *vertex_joints;
    uint16_t joint_count,mesh_count,vertex_count;
    int16_t scale,base_y,walk_rate;
    uint32_t foot_joints;
} animation_package_t;
typedef struct {
    uint32_t clip,phase,grounded,respawns;
    int32_t previous_x,previous_z;
} animation_t;
typedef struct { int16_t r[9]; int32_t t[3]; } animation_matrix_t;
void animation_reset(animation_t *state,const player_t *player,const animation_package_t *package);
void animation_step(animation_t *state,const player_t *player,const animation_package_t *package);
void animation_pose(const animation_t *state,const animation_package_t *package,
                    animation_matrix_t *matrices,scene_vertex_t *vertices);
#endif
