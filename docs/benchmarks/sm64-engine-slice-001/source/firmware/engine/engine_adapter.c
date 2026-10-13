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
struct PlayerCameraState gPlayerCameraState[2];
static struct MarioBodyState engine_body;
static struct Controller engine_controller;
static struct Animation engine_animation;
static struct DmaHandlerList engine_animation_list;
s16 gCurrLevelNum=LEVEL_CASTLE_GROUNDS;
u16 gAreaUpdateCounter;
static uint32_t engine_fault;
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
void sm64_engine_init(const int32_t position[3]){
    struct MarioState empty={0};struct Object object={0};gMarioStates[0]=empty;engine_mario_object=object;
    engine_fault=0;gAreaUpdateCounter=0;engine_load_surfaces();
    engine_controller=(struct Controller){0};engine_body=(struct MarioBodyState){0};engine_camera=(struct Camera){0};
    struct MarioState *m=gMarioState;m->marioObj=gMarioObject;m->area=&engine_area;
    m->area->camera=&engine_camera;m->area->terrainType=TERRAIN_GRASS;
    m->marioBodyState=&engine_body;m->statusForCamera=&gPlayerCameraState[0];m->controller=&engine_controller;
    m->animList=&engine_animation_list;engine_animation_list.bufTarget=&engine_animation;
    m->health=0x880;m->flags=MARIO_NORMAL_CAP|MARIO_CAP_ON_HEAD;m->unkB0=189;
    m->marioObj->header.gfx.animInfo.animID=-1;set_mario_animation(m,MARIO_ANIM_IDLE_HEAD_LEFT);
    vec3f_set(m->pos,(float)position[0],(float)position[1],(float)position[2]);
    m->floorHeight=find_floor(m->pos[0],m->pos[1],m->pos[2],&m->floor);
    if(!m->floor){engine_fault=2;return;}
    m->pos[1]=m->floorHeight;vec3f_copy(m->marioObj->header.gfx.pos,m->pos);m->action=ACT_IDLE;
}
static s32 dispatch(struct MarioState *m){
    switch(m->action){
    case ACT_IDLE:return act_idle(m);
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
    default:engine_fault=m->action;return FALSE;
    }
}
void sm64_engine_update(uint32_t buttons,uint32_t yaw,engine_result_t *result){
    struct MarioState *m=gMarioState;
    if(!engine_fault && !engine_surface_fault){
        struct Controller *c=m->controller;
        float x=(buttons&2u?64.0f:0.0f)-(buttons&1u?64.0f:0.0f);
        float y=(buttons&4u?64.0f:0.0f)-(buttons&8u?64.0f:0.0f);
        if(x!=0.0f && y!=0.0f){x*=0.7071067811865475f;y*=0.7071067811865475f;}
        c->stickX=x;c->stickY=y;c->stickMag=sqrtf(x*x+y*y);
        u16 down=buttons&16u?A_BUTTON:0;c->buttonPressed=down&~c->buttonDown;c->buttonDown=down;
        m->area->camera->yaw=(s16)(yaw<<8);++gAreaUpdateCounter;
        extern u32 gGlobalTimer;++gGlobalTimer;
        mario_reset_bodystate(m);update_mario_inputs(m);
        if(!m->floor)engine_unsupported(0x104);
        for(unsigned loop=0;loop<8 && !engine_fault;++loop){if(!dispatch(m))break;if(loop==7)engine_fault=3;}
        if(m->marioObj->header.gfx.animInfo.curAnim){struct AnimInfo *a=&m->marioObj->header.gfx.animInfo;a->animFrame=geo_update_animation_frame(a,&a->animFrameAccelAssist);a->animTimer=gAreaUpdateCounter;}
        m->marioObj->oPosX=m->pos[0];m->marioObj->oPosY=m->pos[1];m->marioObj->oPosZ=m->pos[2];
    }
    result->x=(int32_t)m->pos[0];result->y=(int32_t)m->pos[1];result->z=(int32_t)m->pos[2];
    result->velocity_y=(int32_t)m->vel[1];result->grounded=!(m->action&ACT_FLAG_AIR);
    result->facing=(uint16_t)m->faceAngle[1]>>11;result->action=m->action;result->fault=engine_fault?engine_fault:engine_surface_fault;
}
uint32_t sm64_engine_probe(uint32_t field){union {float f;uint32_t u;} value;
    switch(field){case 0:return engine_fault;case 1:return gMarioState->action;case 2:value.f=gMarioState->pos[0];return value.u;case 3:value.f=gMarioState->pos[1];return value.u;case 4:value.f=gMarioState->pos[2];return value.u;case 5:return gSurfacesAllocated;case 6:return gSurfaceNodesAllocated;case 7:return engine_surface_bytes();default:return 0;}}
