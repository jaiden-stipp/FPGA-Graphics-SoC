#include "gfx.h"
#include "game_port.h"
#include "portable_data.h"
static player_t player;
static first_person_t camera;
volatile player_t game_player;
int game_port_init(void) {
    player_reset(&player,&portable_world);
    first_person_reset(&camera,&player,&portable_camera);
    return 0;
}
void game_port_update(uint32_t buttons) {
    first_person_step(&camera,&player,&portable_world,&portable_camera,buttons);
    game_player.x=player.x; game_player.y=player.y; game_player.z=player.z;
    game_player.velocity_y=player.velocity_y; game_player.grounded=player.grounded;
    game_player.facing=player.facing; game_player.previous_keys=player.previous_keys;
    game_player.respawns=player.respawns;
}
int game_port_render(uint32_t frame) {
    if(gfx_view_matrix(camera.view) || gfx_begin_frame(frame)) return -1;
    for(uint32_t h=0;h<PORTABLE_WORLD_MESHES;++h)
        if(gfx_draw_mesh((uint8_t)h,0,0,0)) return -1;
    return gfx_end_frame();
}
