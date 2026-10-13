#ifndef WORLD_H
#define WORLD_H
#include "assets.h"
#include "player.h"
#include "camera.h"
// Deferred appearance remains in the asset package until the target supports it.
#define WORLD_RENDER_DEFERRED 1u
typedef struct {scene_mesh_t mesh;int16_t origin[3],bounds[6];uint32_t room_mask,render_flags;} world_chunk_t;
typedef struct {uint32_t floor_start,floor_count,wall_start,wall_count;} world_cell_t;
// Source-defined type IDs stay opaque to the shared engine. The game adapter
// interprets them; geometry and special collision parameters are preserved.
typedef struct {uint16_t type,source;int16_t force;uint8_t room,flags;} world_surface_t;
typedef struct {
    const world_chunk_t *chunks;uint32_t chunk_count;
    const player_world_t *physics;const collision_wall_t *camera_surfaces;uint32_t camera_count;
    const world_cell_t *cells;const uint16_t *floor_indices,*wall_indices;
    int32_t grid_x,grid_z;uint32_t grid_width,grid_depth;
    const int16_t (*floor_normals)[3];
    const uint8_t *floor_rooms;
    const world_surface_t *floor_surfaces,*wall_surfaces;
} world_area_t;
typedef struct {const world_surface_t *surface;const int16_t *normal;int32_t height;} world_contact_t;
typedef struct {
    uint16_t source_area,destination_area;
    int16_t position[3],arrival[3];
    uint16_t radius,required_stars,required_keys;
    uint8_t yaw,automatic;
} world_transition_t;
typedef struct {
    uint16_t source_area,event,destination_area;
    int16_t arrival[3];uint8_t yaw;
} world_exit_t;
void world_select(const world_area_t *area,player_t *player);
void world_collision(const world_area_t *area,const player_t *player);
int world_floor_contact(const world_area_t *area,const player_t *player,world_contact_t *contact);
const world_exit_t *world_exit_find(const world_exit_t *exits,uint32_t count,uint32_t area,uint32_t event);
int world_prepare(const world_area_t *area,const player_t *player,const int16_t view[12],uint32_t reserved);
int world_draw(const world_area_t *area,const player_t *player,const int16_t view[12],uint32_t reserved);
// Source-neutral dynamic instance drawing through the terrain frustum clipper.
// Model vertices use source units; Q8 rotation and translation remain separate.
int world_draw_instance(const scene_mesh_t *mesh,const int32_t position[3],int32_t cosine,int32_t sine,
                        const player_t *player,const int16_t view[12]);
int32_t world_transition_find(const world_transition_t *transitions,uint32_t count,uint32_t area,
    const player_t *player,uint32_t use,uint32_t stars,uint32_t keys);
#endif
