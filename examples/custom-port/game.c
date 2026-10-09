#include "game_port.h"
#include "gfx.h"
#include "portable_data.h"
#if PORTABLE_MESH_COUNT != 2 || PORTABLE_WORLD_MESHES != 1
#error This example expects a floor and a single cube handle.
#endif
static uint32_t yaw;
static int32_t depth;
int game_port_init(void) { yaw=0;depth=256;return 0; }
void game_port_update(uint32_t keys) {
    if((keys&15u)==15u) { yaw=0;depth=256;return; }
    if(keys&1u) yaw=(yaw+3u)&3u;
    if(keys&2u) yaw=(yaw+1u)&3u;
    if(keys&4u) depth+=8;
    if(keys&8u) depth-=8;
    if(depth<0) depth=0;
    if(depth>1024) depth=1024;
}
int game_port_render(uint32_t frame) {
    static const int16_t view[12]={256,0,0,0,0,256,0,-192,0,0,256,1024};
    static const int16_t rotations[4][2]={{256,0},{0,256},{-256,0},{0,-256}};
    int16_t c=rotations[yaw][0],s=rotations[yaw][1];
    int16_t model[12]={c,0,s,0,0,256,0,128,(int16_t)-s,0,c,(int16_t)depth};
    if(gfx_view_matrix(view) || gfx_begin_frame(frame) || gfx_draw_mesh(0,0,0,0) ||
       gfx_draw_matrix(1,model)) return -1;
    return gfx_end_frame();
}
