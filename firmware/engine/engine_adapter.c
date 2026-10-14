// Original Mario actions/step/query math. Platform effects remain explicit.
#include "sm64.h"
#include "game/mario.h"
#include "game/mario_step.h"
#include "game/mario_actions_stationary.h"
#include "game/mario_actions_moving.h"
#include "game/mario_actions_airborne.h"
#include "game/area.h"
#include "game/camera.h"
#include "game/memory.h"
#include "game/interaction.h"
#include "engine/graph_node.h"
#include "engine/math_util.h"
#include "engine/surface_collision.h"
#include "game/mario_misc.h"
#include "engine_slice.h"
#include "actions.inc"
#include "animations.inc"
struct MarioState gMarioStates[2];
struct MarioState *gMarioState=&gMarioStates[0];
static struct Object engine_mario_object;
struct Object *gMarioObject=&engine_mario_object;
static struct Area engine_area;
struct Area *gCurrentArea=&engine_area;
static struct Camera engine_camera;
#define engine_body gBodyStates[0]
static struct Controller engine_controller;
static struct Controller engine_controller2;
struct Controller *gPlayer1Controller=&engine_controller,*gPlayer2Controller=&engine_controller2;
static struct Animation engine_animation;
static struct DmaHandlerList engine_animation_list;
s16 gCurrLevelNum=LEVEL_CASTLE_GROUNDS;
u16 gAreaUpdateCounter;
static uint32_t engine_fault;
static int32_t engine_spawn[3];
static uint32_t engine_spawn_yaw;
static uint32_t engine_respawns;
extern s16 engine_warp_timer;
void engine_reset_swimming(void);
void engine_camera_reset(void);
s32 engine_submerged_action(struct MarioState *m);
void engine_unsupported(uint32_t code){if(!engine_fault)engine_fault=code;}
void engine_load_surfaces(void);
uint32_t engine_surface_bytes(void);
extern uint32_t engine_surface_fault;
extern s32 gSurfacesAllocated,gSurfaceNodesAllocated;
void *segmented_to_virtual(const void *p){return (void *)p;}
// Original animation setters expect DMA into a mutable Animation descriptor.
// The tables/data here already have absolute pointers; returning FALSE prevents
// the original ROM-relative relocation. No values or frame lengths are changed.
s32 load_patchable_table(struct DmaHandlerList *list,s32 index){
    if(index<0 || (unsigned)index>=sizeof(engine_animations)/sizeof(engine_animations[0])){engine_fault=1;return FALSE;}
    *(struct Animation *)list->bufTarget=*engine_animations[index];return FALSE;
}
static void reset_mario(const int32_t position[3]){
    struct MarioState empty={0};struct Object object={0};gMarioStates[0]=empty;engine_mario_object=object;
    engine_fault=0;gAreaUpdateCounter=0;engine_reset_swimming();
    engine_controller=(struct Controller){0};engine_body=(struct MarioBodyState){0};engine_camera=(struct Camera){0};
    struct MarioState *m=gMarioState;m->marioObj=gMarioObject;m->area=&engine_area;
    m->area->camera=&engine_camera;m->area->terrainType=TERRAIN_GRASS;
    m->marioBodyState=&engine_body;m->statusForCamera=&gPlayerCameraState[0];m->controller=&engine_controller;
    m->animList=&engine_animation_list;engine_animation_list.bufTarget=&engine_animation;
    m->health=0x880;m->numLives=4;m->flags=MARIO_NORMAL_CAP|MARIO_CAP_ON_HEAD;m->unkB0=189;
    m->marioObj->header.gfx.animInfo.animID=-1;set_mario_animation(m,MARIO_ANIM_IDLE_HEAD_LEFT);
    vec3f_set(m->pos,(float)position[0],(float)position[1],(float)position[2]);
    m->faceAngle[1]=(s16)engine_spawn_yaw;
    vec3s_copy(m->marioObj->header.gfx.angle,m->faceAngle);
    m->floorHeight=find_floor(m->pos[0],m->pos[1],m->pos[2],&m->floor);
    if(!m->floor){engine_fault=2;return;}
    m->pos[1]=m->floorHeight;vec3f_copy(m->marioObj->header.gfx.pos,m->pos);m->action=ACT_IDLE;
    vec3f_set(m->marioObj->header.gfx.scale,1.0f,1.0f,1.0f);
    engine_area.index=1;update_mario_info_for_cam(m);engine_camera_reset();
}
void sm64_engine_init_heading(const int32_t position[3],uint32_t yaw){
    engine_spawn_yaw=yaw;
    for(unsigned i=0;i<3;++i)engine_spawn[i]=position[i];
    engine_respawns=0;engine_warp_timer=0;engine_load_surfaces();reset_mario(position);
}
void sm64_engine_init(const int32_t position[3]){sm64_engine_init_heading(position,0);}
#ifdef SOC_ENGINE_TEST
// Initial-condition fixture only, absent from the FPGA executable. Original
// actions, geometry queries, damage, health and transitions still execute.
void sm64_engine_test_place(const int32_t position[3],uint32_t action,uint32_t health){
    struct MarioState *m=gMarioState;
    vec3f_set(m->pos,(float)position[0],(float)position[1],(float)position[2]);
    vec3f_set(m->vel,0.0f,0.0f,0.0f);m->forwardVel=0.0f;m->peakHeight=m->pos[1];
    vec3f_copy(m->marioObj->header.gfx.pos,m->pos);
    m->health=(s16)health;set_mario_action(m,action,0);
}
#endif
static s32 dispatch(struct MarioState *m){
    switch(m->action&ACT_GROUP_MASK) {
    case ACT_GROUP_STATIONARY:
        if(check_common_stationary_cancels(m) || mario_update_quicksand(m,0.5f))return TRUE;
        break;
    case ACT_GROUP_MOVING:
        if(check_common_moving_cancels(m) || mario_update_quicksand(m,0.25f))return TRUE;
        break;
    case ACT_GROUP_AIRBORNE:
        if(check_common_airborne_cancels(m))return TRUE;
        play_far_fall_sound(m);break;
    case ACT_GROUP_AUTOMATIC:
        if(check_common_automatic_cancels(m))return TRUE;
        m->quicksandDepth=0.0f;break;
    case ACT_GROUP_SUBMERGED:return engine_submerged_action(m);
    }
    switch(m->action){
    case ACT_IDLE:return act_idle(m);
    case ACT_FIRST_PERSON:return act_first_person(m);
    case ACT_STANDING_AGAINST_WALL:return act_standing_against_wall(m);
    case ACT_WALKING:return act_walking(m);
    case ACT_DECELERATING:return act_decelerating(m);
    case ACT_BRAKING:return act_braking(m);
    case ACT_BRAKING_STOP:return act_braking_stop(m);
    case ACT_TURNING_AROUND:return act_turning_around(m);
    case ACT_FINISH_TURNING_AROUND:return act_finish_turning_around(m);
    case ACT_JUMP:return act_jump(m);
    case ACT_DOUBLE_JUMP:return act_double_jump(m);
    case ACT_TRIPLE_JUMP:return act_triple_jump(m);
    case ACT_FREEFALL:return act_freefall(m);
    case ACT_STEEP_JUMP:return act_steep_jump(m);
    case ACT_FORWARD_ROLLOUT:return act_forward_rollout(m);
    case ACT_BACKWARD_ROLLOUT:return act_backward_rollout(m);
    case ACT_BUTT_SLIDE_AIR:return act_butt_slide_air(m);
    case ACT_SIDE_FLIP:return act_side_flip(m);
    case ACT_SIDE_FLIP_LAND:return act_side_flip_land(m);
    case ACT_SIDE_FLIP_LAND_STOP:return act_side_flip_land_stop(m);
    case ACT_WALL_KICK_AIR:return act_wall_kick_air(m);
    case ACT_AIR_HIT_WALL:return act_air_hit_wall(m);
    case ACT_SOFT_BONK:return act_soft_bonk(m);
    case ACT_BACKWARD_AIR_KB:return act_backward_air_kb(m);
    case ACT_FORWARD_AIR_KB:return act_forward_air_kb(m);
    case ACT_BACKWARD_GROUND_KB:return act_backward_ground_kb(m);
    case ACT_FORWARD_GROUND_KB:return act_forward_ground_kb(m);
    case ACT_HARD_BACKWARD_GROUND_KB:return act_hard_backward_ground_kb(m);
    case ACT_HARD_FORWARD_GROUND_KB:return act_hard_forward_ground_kb(m);
    case ACT_JUMP_LAND:return act_jump_land(m);
    case ACT_DOUBLE_JUMP_LAND:return act_double_jump_land(m);
    case ACT_TRIPLE_JUMP_LAND:return act_triple_jump_land(m);
    case ACT_FREEFALL_LAND:return act_freefall_land(m);
    case ACT_JUMP_LAND_STOP:return act_jump_land_stop(m);
    case ACT_DOUBLE_JUMP_LAND_STOP:return act_double_jump_land_stop(m);
    case ACT_TRIPLE_JUMP_LAND_STOP:return act_triple_jump_land_stop(m);
    case ACT_FREEFALL_LAND_STOP:return act_freefall_land_stop(m);
    case ACT_START_SLEEPING:return act_start_sleeping(m);
    case ACT_SLEEPING:return act_sleeping(m);
    case ACT_WAKING_UP:return act_waking_up(m);
    case ACT_BUTT_SLIDE:return act_butt_slide(m);
    case ACT_STOMACH_SLIDE:return act_stomach_slide(m);
    case ACT_BUTT_SLIDE_STOP:return act_butt_slide_stop(m);
    case ACT_STOMACH_SLIDE_STOP:return act_stomach_slide_stop(m);
    case ACT_PANTING:return act_panting(m);
    case ACT_CROUCHING:return act_crouching(m);
    case ACT_START_CROUCHING:return act_start_crouching(m);
    case ACT_STOP_CROUCHING:return act_stop_crouching(m);
    case ACT_START_CRAWLING:return act_start_crawling(m);
    case ACT_CRAWLING:return act_crawling(m);
    case ACT_CROUCH_SLIDE:return act_crouch_slide(m);
    case ACT_STOP_CRAWLING:return act_stop_crawling(m);
    case ACT_BACKFLIP:return act_backflip(m);
    case ACT_BACKFLIP_LAND:return act_backflip_land(m);
    case ACT_BACKFLIP_LAND_STOP:return act_backflip_land_stop(m);
    case ACT_LONG_JUMP:return act_long_jump(m);
    case ACT_LONG_JUMP_LAND:return act_long_jump_land(m);
    case ACT_LONG_JUMP_LAND_STOP:return act_long_jump_land_stop(m);
    case ACT_GROUND_POUND:return act_ground_pound(m);
    case ACT_GROUND_POUND_LAND:return act_ground_pound_land(m);
    case ACT_DIVE:return act_dive(m);
    case ACT_DIVE_SLIDE:return act_dive_slide(m);
    case ACT_SLIDE_KICK:return act_slide_kick(m);
    case ACT_SLIDE_KICK_SLIDE:return act_slide_kick_slide(m);
    case ACT_SLIDE_KICK_SLIDE_STOP:return act_slide_kick_slide_stop(m);
    case ACT_JUMP_KICK:return act_jump_kick(m);
    case ACT_PUNCHING:return act_punching(m);
    case ACT_MOVE_PUNCHING:return act_move_punching(m);
    case ACT_LEDGE_GRAB:return act_ledge_grab(m);
    case ACT_LEDGE_CLIMB_SLOW_1:return act_ledge_climb_slow(m);
    case ACT_LEDGE_CLIMB_SLOW_2:return act_ledge_climb_slow(m);
    case ACT_LEDGE_CLIMB_DOWN:return act_ledge_climb_down(m);
    case ACT_LEDGE_CLIMB_FAST:return act_ledge_climb_fast(m);
    case ACT_START_HANGING:return act_start_hanging(m);
    case ACT_HANGING:return act_hanging(m);
    case ACT_HANG_MOVING:return act_hang_moving(m);
    case ACT_SQUISHED:return act_squished(m);
    case ACT_WATER_JUMP:return act_water_jump(m);
    case ACT_STANDING_DEATH:return act_standing_death(m);
    case ACT_DEATH_ON_BACK:return act_death_on_back(m);
    case ACT_DEATH_ON_STOMACH:return act_death_on_stomach(m);
    case ACT_SUFFOCATION:return act_suffocation(m);
    case ACT_QUICKSAND_DEATH:return act_quicksand_death(m);
    case ACT_HARD_BACKWARD_AIR_KB:return act_hard_backward_air_kb(m);
    case ACT_HARD_FORWARD_AIR_KB:return act_hard_forward_air_kb(m);
    default:engine_fault=m->action;return FALSE;
    }
}
void sm64_engine_update(uint32_t buttons,uint32_t yaw,engine_result_t *result){
    if(engine_warp_timer>0 && --engine_warp_timer==0){reset_mario(engine_spawn);++engine_respawns;}
    struct MarioState *m=gMarioState;
    if(!engine_fault && !engine_surface_fault){
        struct Controller *c=m->controller;
        float x=(buttons&2u?64.0f:0.0f)-(buttons&1u?64.0f:0.0f);
        float y=(buttons&4u?64.0f:0.0f)-(buttons&8u?64.0f:0.0f);
        if(x!=0.0f && y!=0.0f){x*=0.7071067811865475f;y*=0.7071067811865475f;}
        c->stickX=x;c->stickY=y;c->stickMag=sqrtf(x*x+y*y);
        u16 down=(buttons&16u?A_BUTTON:0)|(buttons&32u?Z_TRIG:0)|(buttons&64u?B_BUTTON:0)
            |(buttons&ENGINE_CAMERA_LEFT?L_CBUTTONS:0)|(buttons&ENGINE_CAMERA_RIGHT?R_CBUTTONS:0)
            |(buttons&ENGINE_CAMERA_UP?U_CBUTTONS:0)|(buttons&ENGINE_CAMERA_DOWN?D_CBUTTONS:0);
        c->buttonPressed=down&~c->buttonDown;c->buttonDown=down;
        // Explicit yaw remains available for deterministic movement diagnostics.
        // Gameplay uses the yaw calculated by the original camera last tick.
        if(yaw!=ENGINE_USE_CAMERA_YAW)m->area->camera->yaw=(s16)(yaw<<8);
        ++gAreaUpdateCounter;
        extern u32 gGlobalTimer;++gGlobalTimer;
        mario_reset_bodystate(m);update_mario_inputs(m);mario_handle_special_floors(m);
        // Upstream geometry-input processing requests death when outside the
        // collision map. Leave action execution suspended until warp recovery.
        for(unsigned loop=0;m->floor && loop<8 && !engine_fault;++loop){if(!dispatch(m))break;if(loop==7)engine_fault=3;}
        if(m->floor && !engine_fault){sink_mario_in_quicksand(m);squish_mario_model(m);update_mario_health(m);update_mario_info_for_cam(m);}
        if(m->marioObj->header.gfx.animInfo.curAnim){struct AnimInfo *a=&m->marioObj->header.gfx.animInfo;a->animFrame=geo_update_animation_frame(a,&a->animFrameAccelAssist);a->animTimer=gAreaUpdateCounter;}
        m->marioObj->oPosX=m->pos[0];m->marioObj->oPosY=m->pos[1];m->marioObj->oPosZ=m->pos[2];
    }
    result->x=(int32_t)m->pos[0];result->y=(int32_t)m->pos[1];result->z=(int32_t)m->pos[2];
    result->velocity_y=(int32_t)m->vel[1];result->grounded=!(m->action&ACT_FLAG_AIR);
    result->facing=(uint16_t)m->faceAngle[1]>>11;result->action=m->action;result->fault=engine_fault?engine_fault:engine_surface_fault;
}
uint32_t sm64_engine_probe(uint32_t field){union {float f;uint32_t u;} value;
    switch(field){case 0:return engine_fault;case 1:return gMarioState->action;case 2:value.f=gMarioState->pos[0];return value.u;case 3:value.f=gMarioState->pos[1];return value.u;case 4:value.f=gMarioState->pos[2];return value.u;case 5:return gSurfacesAllocated;case 6:return gSurfaceNodesAllocated;case 7:return engine_surface_bytes();case 8:return engine_respawns;case 9:return (uint16_t)gMarioState->health;case 10:return (uint16_t)gMarioState->waterLevel;case 11:return (uint16_t)engine_warp_timer;case 12:return gMarioState->input;case 13:value.f=gMarioState->floorHeight;return value.u;case 14:value.f=gMarioState->ceilHeight;return value.u;case 15:return (uint16_t)gMarioState->faceAngle[1];case 16:value.f=gMarioState->floor?gMarioState->floor->normal.y:0.0f;return value.u;default:return 0;}}
