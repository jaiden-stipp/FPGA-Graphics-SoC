#ifndef SM64_ENGINE_SLICE_H
#define SM64_ENGINE_SLICE_H
#include <stdint.h>
typedef struct {int32_t x,y,z,velocity_y;uint32_t grounded,facing,action,fault;} engine_result_t;
#define ENGINE_USE_CAMERA_YAW 256u
#define ENGINE_CAMERA_LEFT 256u
#define ENGINE_CAMERA_RIGHT 512u
#define ENGINE_CAMERA_UP 1024u
#define ENGINE_CAMERA_DOWN 2048u
void sm64_engine_init(const int32_t position[3]);
void sm64_engine_init_heading(const int32_t position[3],uint32_t yaw);
void sm64_engine_update(uint32_t buttons,uint32_t yaw,engine_result_t *result);
uint32_t sm64_engine_probe(uint32_t field);
int sm64_engine_pose(int16_t *xyz,uint32_t vertex_count,uint32_t render_scale);
void sm64_engine_camera_step(int16_t *view,uint32_t render_scale);
uint32_t sm64_engine_visual_probe(uint32_t field);
#endif
