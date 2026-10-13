// Engine compatibility boundary for the source-imported box/star routines.
// Audio/particles/cutscene effects are explicitly omitted; the original state
// machines execute, with integer source-unit object positions and Q8 trig.
#include "castle_gameplay.h"
#include "castle_gameplay_data.h"
#include "castle_transitions.h"
typedef int32_t s32;
typedef uint32_t u32;
typedef uint8_t u8;
#define TRUE 1
#define FALSE 0
#define NULL ((void *)0)
#define MODEL_NONE 0
#define MODEL_STAR 122
#define MODEL_TRANSPARENT_STAR 123
#define SOUND_GENERAL_BREAK_BOX 0
#define SOUND_GENERAL2_STAR_APPEARS 0
#define SOUND_ENV_STAR 0
#define MODEL_CARTOON_STAR 0
#define CUTSCENE_STAR_SPAWN 0
#define TIME_STOP_ENABLED 1u
#define TIME_STOP_MARIO_AND_DOORS 2u
#define ACTIVE_FLAG_INITIATED_TIME_STOP 4u
#define INT_STATUS_INTERACTED 1u
#define INT_SUBTYPE_NO_EXIT 1u
enum {bhvSpawnedStar=1,bhvSparkleSpawn=2};
struct Object {
    int32_t oPosX,oPosY,oPosZ,oHomeX,oHomeY,oHomeZ,oVelY,oGravity,oFloorHeight,oGraphYOffset;
    int32_t oForwardVel,oMoveAngleYaw,oFaceAngleYaw,oAngleVelYaw,oExclamationBoxUnkFC;
    uint32_t oAction,oTimer,oBehParams,oBehParams2ndByte,oAnimState,oInteractStatus,oInteractionSubtype,oFlags,activeFlags;
    struct Object *parentObj;
};
struct Struct802C0DF0 {uint32_t unk0,unk1,unk2,model,behavior;};
struct ObjectHitbox {uint32_t unused;};
static struct Object box,star,mario;
static struct Object *o,*gMarioObject=&mario;
struct CastleCamera {uint32_t cutscene;};
static struct CastleCamera camera_adapter;
static const struct CastleCamera *gCamera=&camera_adapter;
static uint32_t gRecentCutscene,gObjCutsceneDone;
static const uint32_t sCapSaveFlags[3]={0,0,0};
static const struct ObjectHitbox sExclamationBoxHitbox={0},sSparkleSpawnStarHitbox={0};
static struct Struct802C0DF0 sExclamationBoxContents[]={{8,0,0,MODEL_STAR,bhvSpawnedStar},{99,0,0,0,0}};
static uint32_t gCurrSaveFileNum=1,gCurrCourseNum=1,mission,coins,time_stop,previous_buttons;
static uint8_t coin_collected[CASTLE_SLIDE_COIN_COUNT],door_phase[CASTLE_LOCAL_DOOR_COUNT];
static int32_t previous_player_y,previous_player_x,previous_player_z;
static player_t *interaction_player;
static uint32_t save_file_get_flags(void){return 0;}
static uint32_t save_file_get_star_flags(uint32_t file,uint32_t course){(void)file;(void)course;return mission?1u:0u;}
static uint32_t bit_shift_left(uint32_t bit){return bit<32?1u<<bit:0u;}
static void cur_obj_set_model(uint32_t model){(void)model;}
static void obj_mark_for_deletion(struct Object *obj){obj->activeFlags=0;}
static void mark_obj_for_deletion(struct Object *obj){obj_mark_for_deletion(obj);}
static void cur_obj_become_intangible(void){}
static void cur_obj_become_tangible(void){}
static void cur_obj_unhide(void){}
static void cur_obj_hide(void){}
static void obj_set_hitbox(struct Object *obj,const struct ObjectHitbox *hitbox){(void)obj;(void)hitbox;}
static void load_object_collision_model(void) {
    if(o->oAction!=2 || !interaction_player)return;
    game_object_t solid={castle_box_bounds,o->oPosX,o->oPosY,o->oPosZ,0,1,0};
    int32_t previous[3]={previous_player_x,previous_player_y,previous_player_z};
    game_object_resolve_box(&solid,interaction_player,previous,60,160);
}
static uint32_t cur_obj_was_attacked_or_ground_pounded(void){return o->oInteractStatus&INT_STATUS_INTERACTED;}
static void spawn_mist_particles_variable(uint32_t a,uint32_t b,int32_t size){(void)a;(void)b;(void)size;}
static void spawn_mist_particles(void){}
static void create_sound_spawner(uint32_t sound){(void)sound;}
static void cur_obj_play_sound_1(uint32_t sound){(void)sound;}
static void cur_obj_play_sound_2(uint32_t sound){(void)sound;}
static void play_power_star_jingle(uint32_t sound){(void)sound;}
static void cutscene_object(uint32_t scene,struct Object *obj){(void)scene;(void)obj;}
static void set_time_stop_flags(uint32_t flags){time_stop|=flags;}
static void clear_time_stop_flags(uint32_t flags){time_stop&=~flags;}
static struct Object *spawn_object(struct Object *parent,uint32_t model,uint32_t behavior) {
    if(behavior!=bhvSpawnedStar || model!=MODEL_STAR)return NULL;
    struct Object empty={0};star=empty;star.parentObj=parent;star.activeFlags=1;
    star.oPosX=parent->oPosX;star.oPosY=parent->oPosY;star.oPosZ=parent->oPosZ;
    // behavior_data.c bhvSpawnedStar sets its second byte to 1 and then
    // enters the shared SET_HOME/init/loop script. This is not the default
    // zero-byte "move star over Mario" variant.
    star.oBehParams2ndByte=1;star.oHomeX=star.oPosX;star.oHomeY=star.oPosY;star.oHomeZ=star.oPosZ;
    return &star;
}
static uint32_t root(uint32_t x){uint32_t r=0,b=1u<<30;while(b>x)b>>=2;while(b){if(x>=r+b){x-=r+b;r=(r>>1)+b;}else r>>=1;b>>=2;}return r;}
static int32_t divide23(uint32_t n){uint32_t q=0,r=0;for(uint32_t b=32;b;--b){r=(r<<1)|((n>>(b-1))&1u);if(r>=23u){r-=23u;q|=1u<<(b-1);}}return (int32_t)q;}
static int32_t cur_obj_angle_to_home(void) {
    int32_t dx=o->oHomeX-o->oPosX,dz=o->oHomeZ-o->oPosZ,best=-2147483647;uint32_t yaw=0;
    for(uint32_t i=0;i<256;++i){int32_t d=fixed_mul(dx,castle_game_rotations[i][1])+fixed_mul(dz,castle_game_rotations[i][0]);if(d>best){best=d;yaw=i;}}
    return (int32_t)(yaw<<8);
}
static void set_home_to_mario(void) {
    o->oHomeX=mario.oPosX;o->oHomeZ=mario.oPosZ;o->oHomeY=mario.oPosY+250;o->oPosY=o->oHomeY;
    int32_t dx=o->oHomeX-o->oPosX,dz=o->oHomeZ-o->oPosZ;
    o->oForwardVel=divide23(root((uint32_t)(fixed_mul(dx,dx)+fixed_mul(dz,dz))));
}
static void cur_obj_move_using_fvel_and_gravity(void) {
    uint32_t yaw=((uint32_t)o->oMoveAngleYaw>>8)&255u;
    o->oPosX+=(fixed_mul(o->oForwardVel,castle_game_rotations[yaw][1])>>8);
    o->oPosZ+=(fixed_mul(o->oForwardVel,castle_game_rotations[yaw][0])>>8);
    o->oVelY+=o->oGravity;o->oPosY+=o->oVelY;
}
// One original particle scale argument is fractional and purely visual.
// It is removed by the adapter; gameplay statements are source imported.
#include "castle_behaviors.inc"
static int nearby(const player_t *p,int32_t x,int32_t y,int32_t z,int32_t radius,int32_t height) {
    int32_t dx=p->x-x,dz=p->z-z;
    if(dx< -radius || dx>radius || dz< -radius || dz>radius || p->y+160<y || p->y>y+height)return 0;
    return fixed_mul(dx,dx)+fixed_mul(dz,dz)<=fixed_mul(radius,radius);
}
void castle_gameplay_init(void) {
    mission=coins=previous_buttons=time_stop=0;
    for(uint32_t i=0;i<CASTLE_LOCAL_DOOR_COUNT;++i)door_phase[i]=0;
    castle_gameplay_enter(0);
}
void castle_gameplay_enter(uint32_t area) {
    struct Object empty={0};box=star=empty;time_stop=0;previous_player_y=32767;previous_player_x=previous_player_z=0;
    for(uint32_t i=0;i<CASTLE_LOCAL_DOOR_COUNT;++i)door_phase[i]=0;
    for(uint32_t i=0;i<CASTLE_SLIDE_COIN_COUNT;++i)coin_collected[i]=0;
    coins=0;
    if(area==4){box.activeFlags=1;box.oBehParams2ndByte=8;box.oPosX=castle_box_position[0];box.oPosY=box.oHomeY=castle_box_position[1];box.oPosZ=castle_box_position[2];}
}
uint32_t castle_gameplay_stars(void){return 70u+(mission?1u:0u);}
uint32_t castle_gameplay_keys(void){return 3u;}
uint32_t castle_gameplay_frozen(void){return time_stop!=0;}
uint32_t castle_gameplay_mission(void){return mission;}
// Read-only software diagnostics; no MMIO or hardware changes.
int32_t castle_gameplay_probe(uint32_t field) {
    switch(field) {
    case 0:return (int32_t)box.oAction;case 1:return (int32_t)box.activeFlags;
    case 2:return (int32_t)star.oAction;case 3:return (int32_t)star.activeFlags;
    case 4:return star.oPosX;case 5:return star.oPosY;case 6:return star.oPosZ;
    case 7:return (int32_t)mission;case 8:return (int32_t)coins;
    default:return -1;
    }
}
uint32_t castle_gameplay_step(player_t *p,uint32_t area,uint32_t buttons,uint32_t action) {
    interaction_player=p;
    mario.oPosX=p->x;mario.oPosY=p->y;mario.oPosZ=p->z;mario.oMoveAngleYaw=(int32_t)(p->facing<<11);
    uint32_t attack=(buttons&GAME_FIRE) && !(previous_buttons&GAME_FIRE),use=(buttons&GAME_USE) && !(previous_buttons&GAME_USE);
    for(uint32_t i=0;i<CASTLE_LOCAL_DOOR_COUNT;++i) {
        const int16_t *d=castle_local_doors[i];if((uint32_t)d[0]!=area)continue;
        int near=nearby(p,d[1],d[2],d[3],170,300);
        if(near && use && castle_gameplay_stars()>=(uint32_t)d[5])door_phase[i]=90;
        if(door_phase[i])--door_phase[i];
        // Closed-door planar blocker is a scoped replacement for original
        // animated door collision. Reopen nearby doors without changing areas.
        uint32_t yaw=(uint32_t)d[4]&255u;
        int32_t dx=p->x-d[1],dz=p->z-d[3];
        int32_t u=(fixed_mul(dx,castle_game_rotations[yaw][0])-fixed_mul(dz,castle_game_rotations[yaw][1]))>>8;
        int32_t v=(fixed_mul(dx,castle_game_rotations[yaw][1])+fixed_mul(dz,castle_game_rotations[yaw][0]))>>8;
        if(!door_phase[i] && u> -100 && u<100 && v> -40 && v<40 && p->y<d[2]+300 && p->y+160>d[2]) {
            int32_t push=v<0?-40-v:40-v;
            p->x+=(fixed_mul(push,castle_game_rotations[yaw][1])>>8);p->z+=(fixed_mul(push,castle_game_rotations[yaw][0])>>8);
        }
    }
    uint32_t exit=0;
    if(area==4 && box.activeFlags) {
        o=&box;uint32_t old=o->oAction;
        int hit=nearby(p,o->oPosX,o->oPosY-5,o->oPosZ,77,30);
        int stomp=previous_player_y>=o->oPosY+30 && p->y<=o->oPosY+30 && p->velocity_y<=0;
        int head_bump=previous_player_y+160<=o->oPosY-5 && p->y+160>=o->oPosY-5 && p->velocity_y>0;
        int pound_top=action==CASTLE_ACTION_GROUND_POUND && p->velocity_y<=0 && nearby(p,o->oPosX,o->oPosY+castle_box_bounds.max_y-50,o->oPosZ,100,50);
        if((hit && (attack || stomp || head_bump || action==CASTLE_ACTION_GROUND_POUND)) || pound_top)o->oInteractStatus|=INT_STATUS_INTERACTED;
        switch(o->oAction) {
        case 0:exclamation_box_act_0();break;
        case 2:exclamation_box_act_2();break;
        case 3:cur_obj_move_using_fvel_and_gravity();if(o->oVelY<0){o->oVelY=o->oGravity=0;}if(o->oTimer==7)o->oAction=4;break;
        case 4:exclamation_box_act_4();if(star.activeFlags){o=&star;bhv_spawned_star_init();o=&box;}break;
        default:break;
        }
        if(o->oAction!=old)o->oTimer=0;else ++o->oTimer;
    }
    if(area==4 && star.activeFlags) {
        o=&star;uint32_t old=o->oAction;
        if(o->oAction>=3 && nearby(p,o->oPosX,o->oPosY,o->oPosZ,117,50)) {
            o->oInteractStatus|=INT_STATUS_INTERACTED;mission=1;exit=CASTLE_EXIT_STAR;
        }
        bhv_spawned_star_loop();if(o->oAction!=old)o->oTimer=0;else ++o->oTimer;
    }
    if(area==4 && !time_stop)for(uint32_t i=0;i<CASTLE_SLIDE_COIN_COUNT;++i) {
        const int16_t *c=castle_slide_coins[i];
        if(!coin_collected[i] && nearby(p,c[0],c[1],c[2],90,50)){coin_collected[i]=1;++coins;}
    }
    previous_buttons=buttons;previous_player_y=p->y;previous_player_x=p->x;previous_player_z=p->z;return exit;
}
int castle_gameplay_draw(uint32_t area,const player_t *p,const game_view_t *v) {
    // Warp triggers are handled by the world adapter; their source models
    // still need to be drawn, including doors to unsupported destinations.
    for(uint32_t i=0;i<CASTLE_WARP_DOOR_COUNT;++i) {
        const int16_t *d=castle_warp_doors[i];if((uint32_t)d[0]!=area)continue;
        int32_t position[3]={d[1],d[2],d[3]};uint32_t yaw=(uint32_t)d[4]&255u;
        const scene_mesh_t *mesh=d[5]==2?&castle_metal_door_mesh:(d[5]?&castle_castle_door_mesh:&castle_door_mesh);
        if(world_draw_instance(mesh,position,castle_game_rotations[yaw][0],castle_game_rotations[yaw][1],p,v->view))return -1;
    }
    for(uint32_t i=0;i<CASTLE_LOCAL_DOOR_COUNT;++i) {
        const int16_t *d=castle_local_doors[i];if((uint32_t)d[0]!=area)continue;
        int32_t position[3]={d[1],d[2],d[3]};
        uint32_t yaw=((uint32_t)d[4]+(door_phase[i]?64u:0u))&255u;
        const scene_mesh_t *mesh=d[6]?&castle_castle_door_mesh:&castle_door_mesh;
        if(world_draw_instance(mesh,position,castle_game_rotations[yaw][0],castle_game_rotations[yaw][1],p,v->view))return -1;
    }
    if(area==4) {
        if(box.activeFlags){int32_t pos[3]={box.oPosX,box.oPosY,box.oPosZ};if(world_draw_instance(&castle_box_mesh,pos,256,0,p,v->view))return -1;}
        if(star.activeFlags){int32_t pos[3]={star.oPosX,star.oPosY,star.oPosZ};uint32_t yaw=((uint32_t)star.oFaceAngleYaw>>8)&255u;if(world_draw_instance(&castle_star_mesh,pos,castle_game_rotations[yaw][0],castle_game_rotations[yaw][1],p,v->view))return -1;}
        for(uint32_t i=0;i<CASTLE_SLIDE_COIN_COUNT;++i)if(!coin_collected[i]) {
            const int16_t *c=castle_slide_coins[i];int32_t pos[3]={c[0],c[1],c[2]};uint32_t yaw=v->yaw&255u;
            if(world_draw_instance(&castle_coin_mesh,pos,castle_game_rotations[yaw][0],castle_game_rotations[yaw][1],p,v->view))return -1;
        }
    }
    // DRAW_TRIANGLE coordinates are already in view space on this port.
    // An identity HUD view places the overlay at the near plane without
    // changing the GPU view/projection during an active frame.
    game_view_t hud={0,0,{256,0,0,0,0,256,0,0,0,0,256,0}};player_t origin={0};
    if(game_hud_begin(&hud,&origin,0,256))return -1;
    return game_hud_number(8,24,castle_gameplay_stars(),2,CASTLE_HUD_COLOR) ||
           game_hud_number(36,24,coins,2,CASTLE_HUD_COLOR) ||
           game_hud_number(64,24,mission,1,CASTLE_HUD_COLOR);
}
