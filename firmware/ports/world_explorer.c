// Source-neutral, authored two-area demonstration of the same world services.
#include "gfx.h"
#include "game_port.h"
#include "game_services.h"
#include "world_data.h"
#include "portable_data.h"
static player_t player;
static uint32_t area,previous;
static const int16_t view[12]={256,0,0,0,0,256,0,-512,0,0,256,1536};
static const world_transition_t portals[]={
    {0,1,{600,0,600},{0,0,0},100,0,0,0,0},
    {1,0,{600,0,600},{0,0,0},100,0,0,0,0}};
int game_port_init(void) { area=previous=0;world_select(world_areas,&player);return 0; }
void game_port_update(uint32_t word) {
    game_input_t input;game_input_decode(&input,word);
    world_collision(world_areas+area,&player);
    player_step(&player,world_areas[area].physics,input.buttons&31u);
    int32_t i=world_transition_find(portals,2,area,&player,(input.buttons&GAME_USE)&&!(previous&GAME_USE),0,0);
    if(i>=0) { area=portals[i].destination_area;world_select(world_areas+area,&player); }
    previous=input.buttons;
}
int game_port_render(uint32_t frame) {
    if(world_prepare(world_areas+area,&player,view,PORTABLE_MESH_COUNT) || gfx_identity_view() || gfx_begin_frame(frame) ||
       world_draw(world_areas+area,&player,view,PORTABLE_MESH_COUNT))return -1;
    if(gfx_draw_matrix(0,view))return -1;
    return gfx_end_frame();
}
