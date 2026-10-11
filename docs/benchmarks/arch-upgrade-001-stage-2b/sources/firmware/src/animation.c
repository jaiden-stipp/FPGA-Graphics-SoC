#include "animation.h"
#include "cpu_profile.h"

// Q14 rotations use the original 4096 angular samples. Translation retains
// four fractional source-coordinate bits until the final GPU quantization.
static int32_t sine(const animation_package_t *p,uint32_t angle) {
    uint32_t index=(angle&65535u)>>4,quadrant=index>>10;
    index&=1023u;
    int32_t value=p->sines[(quadrant&1u)?1024u-index:index];
    return (quadrant&2u)?-value:value;
}
static int32_t product(int32_t a,int32_t b) { return fixed_mul(a,b)>>14; }
static int32_t channel(const animation_t *s,const animation_package_t *p,uint32_t i) {
    const animation_clip_t *clip=p->clips+s->clip;
    const animation_channel_t *c=clip->channels+i;
    uint32_t frame=(s->phase>>8)-clip->start;
    if (frame>=c->count) frame=c->count-1u;
    return p->values[c->index+frame];
}
static void rotate(animation_matrix_t *m,const animation_t *s,const animation_package_t *p,uint32_t joint) {
    uint32_t x=(uint16_t)channel(s,p,3u+3u*joint),y=(uint16_t)channel(s,p,4u+3u*joint);
    uint32_t z=(uint16_t)channel(s,p,5u+3u*joint);
    int32_t sx=sine(p,x),cx=sine(p,x+16384u),sy=sine(p,y),cy=sine(p,y+16384u);
    int32_t sz=sine(p,z),cz=sine(p,z+16384u),sxsy=product(sx,sy),cxsy=product(cx,sy);
    m->r[0]=(int16_t)product(cy,cz);
    m->r[1]=(int16_t)(product(sxsy,cz)-product(cx,sz));
    m->r[2]=(int16_t)(product(cxsy,cz)+product(sx,sz));
    m->r[3]=(int16_t)product(cy,sz);
    m->r[4]=(int16_t)(product(sxsy,sz)+product(cx,cz));
    m->r[5]=(int16_t)(product(cxsy,sz)-product(sx,cz));
    m->r[6]=(int16_t)-sy; m->r[7]=(int16_t)product(sx,cy); m->r[8]=(int16_t)product(cx,cy);
}
void animation_reset(animation_t *s,const player_t *player,const animation_package_t *p) {
    s->clip=ANIMATION_IDLE; s->phase=(uint32_t)p->clips[ANIMATION_IDLE].start<<8;
    s->grounded=player->grounded; s->respawns=player->respawns;
    s->previous_x=player->x; s->previous_z=player->z;
}
void animation_step(animation_t *s,const player_t *player,const animation_package_t *p) {
    if (s->respawns!=player->respawns) { animation_reset(s,player,p); return; }
    uint32_t moving=(uint32_t)(player->x!=s->previous_x || player->z!=s->previous_z);
    uint32_t selected=moving?ANIMATION_WALK:ANIMATION_IDLE;
    if (!player->grounded) selected=ANIMATION_JUMP;
    else if (!s->grounded) selected=ANIMATION_LAND;
    else if (s->clip==ANIMATION_LAND && s->phase<((uint32_t)(p->clips[ANIMATION_LAND].end-1u)<<8))
        selected=ANIMATION_LAND;
    if (selected!=s->clip) { s->clip=selected; s->phase=(uint32_t)p->clips[selected].start<<8; }
    else {
        const animation_clip_t *clip=p->clips+selected;
        s->phase+=selected==ANIMATION_WALK?(uint32_t)p->walk_rate:256u;
        if (s->phase>=((uint32_t)clip->end<<8)) {
            // The idle wrapper repeats the original center-idle sequence.
            // Jump/land hold their last source frame; walk retains its loop.
            if (selected==ANIMATION_IDLE || !(clip->flags&1u))
                s->phase=((uint32_t)clip->loop<<8)+(s->phase-((uint32_t)clip->end<<8));
            else s->phase=(uint32_t)(clip->end-1u)<<8;
        }
    }
    s->grounded=player->grounded; s->previous_x=player->x; s->previous_z=player->z;
}
void animation_pose(const animation_t *s,const animation_package_t *p,
                    animation_matrix_t *matrices,scene_vertex_t *vertices) {
    DETAIL_START(joints_start);
    for (uint32_t i=0;i<p->joint_count;++i) {
        const animation_joint_t *joint=p->joints+i;
        animation_matrix_t local; rotate(&local,s,p,i);
        int32_t t[3]={(int32_t)joint->x*16,(int32_t)joint->y*16,(int32_t)joint->z*16};
        if (!i) t[1]+=channel(s,p,1u)*16;
        if (joint->parent<0) {
            for (uint32_t k=0;k<9;++k) matrices[i].r[k]=local.r[k];
            for (uint32_t k=0;k<3;++k) matrices[i].t[k]=t[k];
        } else {
            const animation_matrix_t *parent=matrices+joint->parent;
            for (uint32_t row=0;row<3;++row) {
                matrices[i].t[row]=parent->t[row]+((fixed_mul(parent->r[3u*row],t[0])+
                    fixed_mul(parent->r[3u*row+1u],t[1])+fixed_mul(parent->r[3u*row+2u],t[2]))>>14);
                for (uint32_t col=0;col<3;++col) matrices[i].r[3u*row+col]=(int16_t)(
                    (fixed_mul(parent->r[3u*row],local.r[col])+
                     fixed_mul(parent->r[3u*row+1u],local.r[col+3u])+
                     fixed_mul(parent->r[3u*row+2u],local.r[col+6u]))>>14);
            }
        }
    }
    DETAIL_END(PROFILE_JOINTS,joints_start);
    DETAIL_START(skin_start);
    uint32_t index=0; int32_t sole=32767;
    for (uint32_t mesh=0;mesh<p->mesh_count;++mesh) {
        const scene_mesh_t *m=p->meshes+mesh;
        for (uint32_t v=0;v<m->vertex_count;++v,++index) {
            const scene_vertex_t *local=m->vertices+v;
            const animation_matrix_t *matrix=matrices+p->vertex_joints[index];
            int32_t q[3];
            for (uint32_t row=0;row<3;++row) q[row]=matrix->t[row]+((
                fixed_mul(matrix->r[3u*row],local->x)+fixed_mul(matrix->r[3u*row+1u],local->y)+
                fixed_mul(matrix->r[3u*row+2u],local->z))>>10);
            vertices[index].x=(int16_t)(fixed_mul(q[0],p->scale)>>18);
            vertices[index].y=(int16_t)(fixed_mul(q[1]-p->base_y,p->scale)>>18);
            vertices[index].z=(int16_t)(fixed_mul(q[2],p->scale)>>18);
            if ((p->foot_joints&(1u<<p->vertex_joints[index])) && vertices[index].y<sole)
                sole=vertices[index].y;
        }
    }
    // A common render translation places the lower foot sole on the collision
    // floor. It does not deform parts or feed root motion into player physics.
    if (s->grounded && sole!=32767)
        for (uint32_t i=0;i<index;++i) vertices[i].y=(int16_t)(vertices[i].y-sole);
    DETAIL_END(PROFILE_SKIN,skin_start);
}
