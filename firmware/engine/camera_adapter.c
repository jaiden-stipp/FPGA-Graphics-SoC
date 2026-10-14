// Include unchanged camera routines to access their internal state. This adapter
// schedules normal grounds modes; NPC/object cutscenes and other areas are absent.
#include "src/game/camera.c"
#include "engine_slice.h"
void engine_unsupported(u32 code);
void engine_camera_reset(void){
    struct Camera *c=gMarioState->area->camera;
    gLakituState=(struct LakituState){0};sModeInfo=(struct ModeTransitionInfo){0};
    sSelectionFlags=0;c->mode=c->defMode=CAMERA_MODE_8_DIRECTIONS;
    reset_camera(c);init_camera(c);
    gCameraMovementFlags&=~CAM_MOVE_INIT_CAMERA;
    sStatusFlags|=CAM_FLAG_FRAME_AFTER_CAM_INIT;
}
void sm64_engine_camera_step(int16_t *view,uint32_t render_scale){
    struct Camera *c=gMarioState->area->camera;Mat4 matrix;Vec3f relative;
    if(!render_scale || render_scale>4){engine_unsupported(0x201);return;}
    gCamera=c;
    sMarioGeometry.prevFloorHeight=sMarioGeometry.currFloorHeight;
    sMarioGeometry.prevCeilHeight=sMarioGeometry.currCeilHeight;
    sMarioGeometry.prevFloor=sMarioGeometry.currFloor;sMarioGeometry.prevCeil=sMarioGeometry.currCeil;
    sMarioGeometry.prevFloorType=sMarioGeometry.currFloorType;sMarioGeometry.prevCeilType=sMarioGeometry.currCeilType;
    find_mario_floor_and_ceil(&sMarioGeometry);gCheckingSurfaceCollisionsForCamera=TRUE;
    vec3f_copy(c->pos,gLakituState.goalPos);vec3f_copy(c->focus,gLakituState.goalFocus);
    c->yaw=gLakituState.yaw;c->nextYaw=gLakituState.nextYaw;c->mode=gLakituState.mode;c->defMode=gLakituState.defMode;
    sCButtonsPressed=find_c_buttons_pressed(sCButtonsPressed,gPlayer1Controller->buttonPressed,gPlayer1Controller->buttonDown);
    sYawSpeed=0x400;
    switch(c->mode){
    case CAMERA_MODE_CLOSE:case CAMERA_MODE_FREE_ROAM:mode_lakitu_camera(c);break;
    case CAMERA_MODE_WATER_SURFACE:mode_water_surface_camera(c);break;
    case CAMERA_MODE_BEHIND_MARIO:mode_behind_mario_camera(c);break;
    case CAMERA_MODE_C_UP:mode_c_up_camera(c);break;
    case CAMERA_MODE_8_DIRECTIONS:mode_8_directions_camera(c);break;
    default:engine_unsupported(0x202);break;
    }
    gCheckingSurfaceCollisionsForCamera=FALSE;update_lakitu(c);
    gCheckingSurfaceCollisionsForCamera=FALSE;
    gLakituState.lastFrameAction=sMarioCamState->action;sStatusFlags&=~CAM_FLAG_FRAME_AFTER_CAM_INIT;
    mtxf_lookat(matrix,gLakituState.pos,gLakituState.focus,gLakituState.roll);
    for(unsigned k=0;k<3;++k)relative[k]=(gLakituState.pos[k]-gMarioState->pos[k])*render_scale;
    for(unsigned row=0;row<3;++row){
        float sign=row==2?-1.0f:1.0f;float translation=0;
        for(unsigned k=0;k<3;++k){float r=matrix[k][row]*sign;view[row*4+k]=(s16)(r*256.0f);translation-=r*relative[k];}
        if(!(translation>=-32768.0f && translation<=32767.0f)){engine_unsupported(0x203);return;}
        view[row*4+3]=(s16)translation;
    }
}
