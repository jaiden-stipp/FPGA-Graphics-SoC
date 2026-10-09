#include "soc.h"
#include "gfx.h"
#include "game_port.h"
#include "game_services.h"
#include "portable_data.h"
#include "quake_demo_data.h"
static player_t player;
static game_view_t camera;
static game_object_t door,pickup,enemy;
static uint32_t tick,previous,opening,health,armor,ammo,enemy_health,last_upload,fire_cooldown,hurt_cooldown;
volatile player_t game_player;
volatile uint32_t demo_state[10];
static void object(game_object_t *o,const game_bounds_t *bounds,const int16_t p[3]) {
    o->local=*bounds;o->x=p[0];o->y=p[1];o->z=p[2];o->phase=0;o->enabled=1;o->frame=0;
}
static void reset(void) {
    player_reset(&player,&portable_world);camera.yaw=portable_camera.initial_yaw<<2;camera.pitch=0;
    object(&door,&demo_door_bounds,demo_door_position);
    object(&pickup,&demo_pickup_bounds,demo_pickup_position);
    object(&enemy,&demo_enemy_bounds,demo_enemy_position);
    tick=0;opening=0;health=100;armor=0;ammo=20;enemy_health=30;
    last_upload=0xffffffffu;fire_cooldown=0;hurt_cooldown=0;
}
int game_port_init(void) { if(SOC_INPUT_ABI!=0x494e0101u)return -1;reset();return 0; }
static int near(const game_object_t *o,int32_t range) {
    return player.x>o->x-range && player.x<o->x+range && player.z>o->z-range && player.z<o->z+range;
}
void game_port_update(uint32_t word) {
    game_input_t input;game_input_decode(&input,word);
    if((input.buttons&GAME_RESET) && !(previous&GAME_RESET)){reset();previous=input.buttons;return;}
    if(input.has_look){camera.yaw=input.yaw;camera.pitch=input.pitch;}
    else {if((input.buttons&3u)==1u)camera.yaw=(camera.yaw+252u)&255u;
          if((input.buttons&3u)==2u)camera.yaw=(camera.yaw+4u)&255u;}
    uint32_t keys=game_movement_keys(&input,camera.yaw);
    if(!input.has_look) { game_input_t legacy=input;legacy.buttons&=~3u;keys=game_movement_keys(&legacy,camera.yaw); }
    int32_t old_x=player.x,old_y=player.y,old_z=player.z;
    player_step(&player,&portable_world,keys);
    if(game_object_overlap(&door,&player,portable_world.radius,portable_world.height)){
        player.x=old_x;player.y=old_y;player.z=old_z;
    }
    if((input.buttons&GAME_USE) && !(previous&GAME_USE) && near(&door,600))opening=!opening;
    int32_t old_phase=door.phase;
    game_door_step(&door,(int)opening,48,600);door.y=demo_door_position[1]+door.phase;
    if(game_object_overlap(&door,&player,portable_world.radius,portable_world.height)){
        door.phase=old_phase;door.y=demo_door_position[1]+old_phase;opening=1;
    }
    if(game_pickup_step(&pickup,&player,portable_world.radius,portable_world.height))armor=50;
    if(enemy.enabled) {
        // Explicit demo patrol on original collision floors, not Quake AI.
        uint32_t cycle=tick&127u;enemy.x=demo_enemy_position[0]+(cycle<64u?(int32_t)cycle*4:(int32_t)(128u-cycle)*4);
        int32_t floor=player_floor(&portable_world,enemy.x,enemy.z,enemy.y+72);
        if(floor!= -32768)enemy.y=floor;
        enemy.frame=game_animation_frame(tick,4,DEMO_ENEMY_FRAMES);
    }
    game_view_update(&camera,&player,portable_camera.eye_height,demo_rotations);
    if(fire_cooldown)--fire_cooldown;if(hurt_cooldown)--hurt_cooldown;
    if((input.buttons&GAME_FIRE) && !fire_cooldown && ammo) {
        --ammo;fire_cooldown=6;
        int32_t x=enemy.x-player.x,y=enemy.y+112-player.y-portable_camera.eye_height,z=enemy.z-player.z;
        int32_t sx=(fixed_mul(camera.view[0],x)+fixed_mul(camera.view[2],z))>>8;
        int32_t sy=(fixed_mul(camera.view[4],x)+fixed_mul(camera.view[5],y)+fixed_mul(camera.view[6],z))>>8;
        int32_t depth=(fixed_mul(camera.view[8],x)+fixed_mul(camera.view[9],y)+fixed_mul(camera.view[10],z))>>8;
        if(enemy.enabled && depth>=257 && sx*160> -depth*18 && sx*160<depth*18 && sy*160> -depth*24 && sy*160<depth*24) {
            enemy_health-=10;if(!enemy_health)enemy.enabled=0;
        }
    }
    if(enemy.enabled && !hurt_cooldown && near(&enemy,180) && player.y<enemy.y+224 && player.y+224>enemy.y) {
        uint32_t damage=10;
        if(armor){uint32_t absorbed=armor<5u?armor:5u;armor-=absorbed;damage-=absorbed;}
        health=health>damage?health-damage:0;hurt_cooldown=30;
    }
    if(!health || player.respawns){reset();player.respawns=0;}
    previous=input.buttons;++tick;
    game_player=player;
    demo_state[0]=health;demo_state[1]=armor;demo_state[2]=ammo;demo_state[3]=(uint32_t)door.phase;
    demo_state[4]=pickup.enabled;demo_state[5]=enemy_health;demo_state[6]=enemy.frame;
    demo_state[7]=camera.yaw;demo_state[8]=(uint32_t)camera.pitch;demo_state[9]=tick;
}
static int draw(uint32_t first,uint32_t count,const game_object_t *o,uint32_t yaw) {
    if(!o->enabled)return 0;
    int16_t matrix[12]={256,0,0,0,0,256,0,0,0,0,256,0};
    matrix[0]=demo_rotations[yaw&255u][0];matrix[2]=demo_rotations[yaw&255u][1];
    matrix[8]=(int16_t)-matrix[2];matrix[10]=matrix[0];
    matrix[3]=(int16_t)o->x;matrix[7]=(int16_t)o->y;matrix[11]=(int16_t)o->z;
    for(uint32_t h=first;h<first+count;++h)if(gfx_draw_matrix((uint8_t)h,matrix))return -1;
    return 0;
}
int game_port_render(uint32_t frame) {
    if(enemy.enabled && enemy.frame!=last_upload){if(demo_enemy_upload(enemy.frame))return -1;last_upload=enemy.frame;}
    if(gfx_projection(PORTABLE_FOCAL,PORTABLE_NEAR_Z) || gfx_view_matrix(camera.view) || gfx_begin_frame(frame))return -1;
    for(uint32_t h=0;h<PORTABLE_WORLD_MESHES;++h)if(gfx_draw_mesh((uint8_t)h,0,0,0))return -1;
    if(draw(DEMO_DOOR_FIRST,DEMO_DOOR_COUNT,&door,0) || draw(DEMO_PICKUP_FIRST,DEMO_PICKUP_COUNT,&pickup,(tick<<2)&255u) ||
       draw(DEMO_ENEMY_FIRST,DEMO_ENEMY_COUNT,&enemy,192))return -1;
    if(game_hud_begin(&camera,&player,portable_camera.eye_height,PORTABLE_FOCAL) || game_hud_rect(0,218,320,22,DEMO_BLACK) ||
       game_hud_number(8,222,health,3,DEMO_RED) || game_hud_number(70,222,armor,2,DEMO_GOLD) ||
       game_hud_number(120,222,ammo,2,DEMO_WHITE) ||
       game_hud_rect(180,224,32,8,DEMO_RED) ||
       game_hud_rect(180,224,(int16_t)(enemy_health+1),8,DEMO_GREEN) ||
       game_hud_rect(232,224,(int16_t)((door.phase>>4)+1),8,DEMO_GOLD) ||
       game_hud_rect(300,224,8,8,pickup.enabled?DEMO_GOLD:DEMO_GREEN) ||
       game_hud_rect(155,119,3,2,DEMO_WHITE) || game_hud_rect(162,119,3,2,DEMO_WHITE) ||
       game_hud_rect(159,115,2,3,DEMO_WHITE) || game_hud_rect(159,122,2,3,DEMO_WHITE))return -1;
    return gfx_end_frame();
}
