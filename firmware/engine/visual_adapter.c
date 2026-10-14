// Renderer bridge: original channels, hierarchy, SDK matrices and body callbacks.
// The imported low-poly mesh's fixed material/eye/hand switches remain unchanged.
#include "sm64.h"
#include "game/mario.h"
#include "game/level_update.h"
#include "game/mario_misc.h"
#include "game/camera.h"
#include "engine/graph_node.h"
#include "engine/math_util.h"
#include "engine_slice.h"
#include "visual.inc"
struct GraphNodeCamera *gCurGraphNodeCamera;
static Mat4 bones[ENGINE_VISUAL_JOINTS];
static s32 packed_bones[ENGINE_VISUAL_JOINTS][12];
static struct GraphNodeCamera camera_node;
uint32_t sm64_engine_visual_probe(uint32_t field){
    struct AnimInfo *a=&gMarioState->marioObj->header.gfx.animInfo;
    union{float f;uint32_t u;} value;
    switch(field){
    case 0:return (uint16_t)a->animID;case 1:return (uint16_t)a->animFrame;
    case 2:return gMarioState->area->camera->mode;case 3:return (uint16_t)gMarioState->area->camera->yaw;
    case 4:case 5:case 6:value.f=gLakituState.pos[field-4];return value.u;
    case 7:case 8:case 9:value.f=gLakituState.focus[field-7];return value.u;
    default:return 0;
    }
}
#ifdef SOC_ENGINE_TEST
uint32_t sm64_engine_test_animation(uint32_t id,uint32_t frame){
    set_mario_animation(gMarioState,(s32)id);
    struct AnimInfo *a=&gMarioState->marioObj->header.gfx.animInfo;
    if(frame<(uint32_t)a->curAnim->loopEnd)a->animFrame=(s16)frame;
    return a->curAnim->loopEnd;
}
#endif
static void rotation_callback(Vec3s rotation,int head){
    struct GraphNodeGenerated generated={0};struct GraphNodeRotation node={0};
    generated.fnNode.node.next=&node.node;
    if(head)geo_mario_head_rotation(GEO_CONTEXT_RENDER,&generated.fnNode.node,0);
    else geo_mario_tilt_torso(GEO_CONTEXT_RENDER,&generated.fnNode.node,0);
    vec3s_copy(rotation,node.rotation);
}
static float part_scale(unsigned parameter){
    struct GraphNodeGenerated generated={0};struct GraphNodeScale node={0};
    generated.parameter=parameter;generated.fnNode.node.next=&node.node;
    geo_mario_hand_foot_scaler(GEO_CONTEXT_RENDER,&generated.fnNode.node,0);
    return node.scale;
}
static int pose_vertices(int16_t *xyz,uint32_t count,uint32_t render_scale,int float_reference){
    struct MarioState *m=gMarioState;struct AnimInfo *info=&m->marioObj->header.gfx.animInfo;
    struct Animation *anim=info->curAnim;
    if(count!=ENGINE_VISUAL_VERTICES || !anim || !render_scale || render_scale>4)return -1;
    camera_node.config.camera=m->area->camera;gCurGraphNodeCamera=&camera_node;
    // Initialization has not rendered/advanced frame -1 yet. Sample frame zero
    // without advancing engine state a second time.
    s32 frame=info->animFrame<0?0:info->animFrame;u16 *index=(u16 *)anim->index;
    float multiplier=anim->animYTransDivisor?(float)info->animYTrans/anim->animYTransDivisor:1.0f;
    Vec3f root={0,0,0};Vec3s torso,head;Mat4 outer,local,parent,rot;
    int enabled=!(anim->flags&ANIM_FLAG_5);
    if(enabled)for(unsigned axis=0;axis<3;++axis){
        s16 sample=anim->values[retrieve_animation_index(frame,&index)];
        int use=!(anim->flags&ANIM_FLAG_6);
        if(anim->flags&ANIM_FLAG_HOR_TRANS)use=axis==1;
        else if(anim->flags&ANIM_FLAG_VERT_TRANS)use=axis!=1;
        if(use)root[axis]=sample*multiplier;
    }
    rotation_callback(torso,0);rotation_callback(head,1);
    Vec3f offset,scale;
    for(unsigned axis=0;axis<3;++axis){
        offset[axis]=m->marioObj->header.gfx.pos[axis]-m->pos[axis];
        scale[axis]=m->marioObj->header.gfx.scale[axis]*(ENGINE_MODEL_SCALE_Q16/65536.0f);
    }
    mtxf_rotate_zxy_and_translate(local,offset,m->marioObj->header.gfx.angle);
    mtxf_scale_vec3f(outer,local,scale);
    for(unsigned joint=0;joint<ENGINE_VISUAL_JOINTS;++joint){
        Vec3f translation;Vec3s angle={0,0,0};
        for(unsigned axis=0;axis<3;++axis){
            translation[axis]=visual_joints[joint][axis+1]+(joint==0?root[axis]:0.0f);
            if(enabled)angle[axis]=anim->values[retrieve_animation_index(frame,&index)];
        }
        int p=visual_joints[joint][0];mtxf_copy(parent,p<0?outer:bones[p]);
        if(joint==ENGINE_TORSO_JOINT){
            mtxf_rotate_zxy_and_translate(rot,gVec3fZero,torso);mtxf_mul(local,rot,parent);mtxf_copy(parent,local);
        }
        mtxf_rotate_xyz_and_translate(local,translation,angle);mtxf_mul(bones[joint],local,parent);
        if(joint==ENGINE_HEAD_JOINT){
            mtxf_rotate_zxy_and_translate(rot,gVec3fZero,head);mtxf_mul(local,rot,bones[joint]);mtxf_copy(bones[joint],local);
        }
    }
    float left=part_scale(1),right=part_scale(0),foot=part_scale(2);
    if(!float_reference)for(unsigned joint=0;joint<ENGINE_VISUAL_JOINTS;++joint){
        float size=joint==ENGINE_LEFT_HAND_JOINT?left:joint==ENGINE_RIGHT_HAND_JOINT?right:joint==ENGINE_RIGHT_FOOT_JOINT?foot:1.0f;
        for(unsigned axis=0;axis<3;++axis){
            float t=bones[joint][3][axis]*render_scale;
            if(!(t>=-32768.0f && t<=32767.0f))return -1;
            packed_bones[joint][axis*4+3]=(s32)(t*16384.0f);
            for(unsigned k=0;k<3;++k){
                float q=(bones[joint][k][axis]*size)*render_scale;
                if(!(q>=-4.0f && q<=4.0f))return -1;
                packed_bones[joint][axis*4+k]=(s32)(q*16384.0f);
            }
        }
    }
    for(unsigned vertex=0;vertex<count;++vertex){
        unsigned joint=visual_bindings[vertex];float size=joint==ENGINE_LEFT_HAND_JOINT?left:joint==ENGINE_RIGHT_HAND_JOINT?right:joint==ENGINE_RIGHT_FOOT_JOINT?foot:1.0f;
        for(unsigned axis=0;axis<3;++axis){
            if(!float_reference){
                s32 q=packed_bones[joint][axis*4+3];
                // Generator proves raw coordinates <=4096. With admitted
                // coefficients <=65536, all products and sums fit int32.
                for(unsigned k=0;k<3;++k)q+=visual_vertices[vertex][k]*packed_bones[joint][axis*4+k];
                q/=16384; // C truncation toward zero, matching float conversion.
                if(q< -32768 || q>32767)return -1;
                xyz[vertex*3+axis]=(s16)q;continue;
            }
            float q=bones[joint][3][axis];
            for(unsigned k=0;k<3;++k)q+=(visual_vertices[vertex][k]*size)*bones[joint][k][axis];
            q*=render_scale;
            if(!(q>=-32768.0f && q<=32767.0f))return -1;
            xyz[vertex*3+axis]=(s16)q;
        }
    }
    return 0;
}
int sm64_engine_pose(int16_t *xyz,uint32_t count,uint32_t render_scale){
#ifdef SOC_VISUAL_FLOAT_REFERENCE
    return pose_vertices(xyz,count,render_scale,1);
#else
    return pose_vertices(xyz,count,render_scale,0);
#endif
}
#ifdef SOC_ENGINE_TEST
int sm64_engine_test_float_pose(int16_t *xyz,uint32_t count,uint32_t render_scale){return pose_vertices(xyz,count,render_scale,1);}
#endif
