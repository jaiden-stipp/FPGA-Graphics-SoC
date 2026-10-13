#ifndef SM64_ENGINE_SLICE_H
#define SM64_ENGINE_SLICE_H
#include <stdint.h>
typedef struct {int32_t x,y,z,velocity_y;uint32_t grounded,facing,action,fault;} engine_result_t;
void sm64_engine_init(const int32_t position[3]);
void sm64_engine_update(uint32_t buttons,uint32_t yaw,engine_result_t *result);
uint32_t sm64_engine_probe(uint32_t field);
#endif
