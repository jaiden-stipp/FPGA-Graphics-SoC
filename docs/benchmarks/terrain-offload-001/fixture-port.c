#include "soc.h"
#include "gfx.h"
#include "world.h"
#include "portable_data.h"
static player_t player;
volatile player_t game_player;
static const int16_t view[12]={256,0,0,0,0,256,0,0,0,0,256,0};
int game_port_init(void){world_select(world_areas,&player);game_player=player;return 0;}
void game_port_update(uint32_t input){(void)input;}
int game_port_render(uint32_t frame){
    if(world_prepare(world_areas,&player,view,PORTABLE_MESH_COUNT) || gfx_identity_view() || gfx_begin_frame(frame))return -1;
    if(world_draw(world_areas,&player,view,PORTABLE_MESH_COUNT))return -1;
    return gfx_end_frame();
}
