#include "camera.h"

static int32_t magnitude(int32_t x) { return x<0?-x:x; }
static int32_t clamp(int32_t x, int32_t limit) {
    return x>limit?limit:(x<-limit?-limit:x);
}
static int32_t filter(int32_t value, int32_t target, int32_t shift) {
    int32_t delta=target-value;
    if (magnitude(delta)<(1<<shift)) return target;
    return value+(delta>>shift);
}
static int32_t ratio(int32_t numerator, int32_t denominator) {
    uint32_t a=(uint32_t)numerator<<8, b=(uint32_t)denominator, result=0, bit=1;
    if (!b) return 0;
    while (b<=(a>>1)) { b<<=1; bit<<=1; }
    while (bit) { if (a>=b) { a-=b; result|=bit; } b>>=1; bit>>=1; }
    return (int32_t)result;
}
static int32_t plane(const collision_wall_t *s, int32_t x, int32_t y, int32_t z) {
    return (fixed_mul(s->nx,x-s->a.x)+fixed_mul(s->ny,y-s->a.y)+fixed_mul(s->nz,z-s->a.z))>>12;
}
static int expanded_triangle(const collision_wall_t *s, int32_t x, int32_t y, int32_t z, int32_t radius) {
    int32_t distance=plane(s,x,y,z);
    x-=fixed_mul(s->nx,distance)>>12;
    y-=fixed_mul(s->ny,distance)>>12;
    z-=fixed_mul(s->nz,distance)>>12;
    const collision_point_t *points[3]={&s->a,&s->b,&s->c};
    int positive=1,negative=1;
    for (uint32_t i=0;i<3;++i) {
        const collision_point_t *a=points[i], *b=points[i==2?0:i+1];
        int32_t u,v,pu,pv;
        if (s->axis==0) { u=b->y-a->y; v=b->z-a->z; pu=y-a->y; pv=z-a->z; }
        else if (s->axis==1) { u=b->x-a->x; v=b->z-a->z; pu=x-a->x; pv=z-a->z; }
        else { u=b->x-a->x; v=b->y-a->y; pu=x-a->x; pv=y-a->y; }
        int32_t edge=fixed_mul(u,pv)-fixed_mul(v,pu);
        int32_t tolerance=fixed_mul(radius,magnitude(u)+magnitude(v));
        if (edge<-tolerance) positive=0;
        if (edge>tolerance) negative=0;
    }
    return positive || negative;
}
// Continuous segment/expanded-plane test. The finite triangle check is
// conservative near edges, so the boom retracts rather than grazing a corner.
static int32_t sweep(const camera_world_t *world, int32_t ax, int32_t ay, int32_t az,
                     int32_t bx, int32_t by, int32_t bz, int32_t clearance) {
    int32_t best=256,dx=bx-ax,dy=by-ay,dz=bz-az;
    if (!(dx || dy || dz)) return best;
    for (uint32_t i=0;i<world->count;++i) {
        const collision_wall_t *s=world->surfaces+i;
        if ((ax<s->min_x-clearance && bx<s->min_x-clearance) ||
            (ax>s->max_x+clearance && bx>s->max_x+clearance) ||
            (ay<s->min_y-clearance && by<s->min_y-clearance) ||
            (ay>s->max_y+clearance && by>s->max_y+clearance) ||
            (az<s->min_z-clearance && bz<s->min_z-clearance) ||
            (az>s->max_z+clearance && bz>s->max_z+clearance)) continue;
        int32_t start=plane(s,ax,ay,az),end=plane(s,bx,by,bz),margin=clearance;
        // An anchor already closer than the preferred margin may move away
        // or parallel, but cannot cross the face to escape it.
        if (magnitude(start)<=margin) margin=magnitude(start)>1?magnitude(start)-1:0;
        int32_t numerator,denominator;
        if (start>0 && end<margin) { numerator=start-margin; denominator=start-end; }
        else if (start<0 && end>-margin) { numerator=-start-margin; denominator=end-start; }
        else if (!start && end && expanded_triangle(s,ax,ay,az,clearance)) return 0;
        else continue;
        int32_t t=ratio(numerator,denominator);
        if (t>best) continue;
        int32_t x=ax+(fixed_mul(dx,t)>>8),y=ay+(fixed_mul(dy,t)>>8),z=az+(fixed_mul(dz,t)>>8);
        if (expanded_triangle(s,x,y,z,clearance)) best=t>2?t-2:0;
    }
    return best;
}
int32_t camera_boom(const camera_world_t *w,int32_t ax,int32_t ay,int32_t az,
                    int32_t bx,int32_t by,int32_t bz,int32_t clearance) {
    return sweep(w,ax,ay,az,bx,by,bz,clearance);
}
void camera_orbit_step(camera_orbit_t *c,const player_t *p,
                       const camera_orbit_config_t *cfg,const camera_world_t *world,
                       int16_t v[12],int32_t scale) {
    if(!c->initialized || c->respawns!=p->respawns ||
       magnitude(p->x-c->previous_x)>cfg->snap_distance ||
       magnitude(p->y-c->previous_y)>cfg->snap_distance ||
       magnitude(p->z-c->previous_z)>cfg->snap_distance) {
        c->focus_x=p->x;c->focus_y=p->y+cfg->target_height;c->focus_z=p->z;
        c->fraction=256;c->initialized=1;
    }else {
        c->focus_x=filter(c->focus_x,p->x,(int32_t)cfg->follow_shift);
        c->focus_y=filter(c->focus_y,p->y+cfg->target_height,(int32_t)cfg->vertical_shift);
        c->focus_z=filter(c->focus_z,p->z,(int32_t)cfg->follow_shift);
    }
    c->previous_x=p->x;c->previous_y=p->y;c->previous_z=p->z;c->respawns=p->respawns;
    int32_t ax=p->x,ay=p->y+cfg->target_height,az=p->z;
    int32_t ex=c->focus_x-(fixed_mul(cfg->distance,v[8])>>8);
    int32_t ey=c->focus_y-(fixed_mul(cfg->distance,v[9])>>8);
    int32_t ez=c->focus_z-(fixed_mul(cfg->distance,v[10])>>8);
    int32_t allowed=sweep(world,ax,ay,az,ex,ey,ez,cfg->clearance);
    if(allowed<c->fraction)c->fraction=allowed;
    else {c->fraction+=(int32_t)cfg->recovery_step;if(c->fraction>allowed)c->fraction=allowed;}
    int32_t dx=fixed_mul((fixed_mul(ex-ax,c->fraction)>>8),scale);
    int32_t dy=fixed_mul(cfg->target_height+(fixed_mul(ey-ay,c->fraction)>>8),scale);
    int32_t dz=fixed_mul((fixed_mul(ez-az,c->fraction)>>8),scale);
    for(uint32_t row=0;row<3;++row) {
        uint32_t b=row<<2;
        v[b+3]=(int16_t)-((fixed_mul(dx,v[b])+fixed_mul(dy,v[b+1])+fixed_mul(dz,v[b+2]))>>8);
    }
}
static void frame(camera_t *c, const player_t *p, const camera_config_t *cfg, const camera_world_t *world) {
    int32_t ax=p->x,ay=p->y+cfg->target_height,az=p->z;
    int32_t target=sweep(world,ax,ay,az,c->target_x,c->target_y,c->target_z,cfg->clearance);
    int32_t tx=ax+(fixed_mul(c->target_x-ax,target)>>8);
    int32_t ty=ay+(fixed_mul(c->target_y-ay,target)>>8);
    int32_t tz=az+(fixed_mul(c->target_z-az,target)>>8);
    int32_t best=-1,selected=0;
    for (uint32_t i=0;i<cfg->pitch_count;++i) {
        int32_t y=ty+(fixed_mul(cfg->distance,cfg->pitches[i][1])>>8);
        int32_t z=tz-(fixed_mul(cfg->distance,cfg->pitches[i][0])>>8);
        int32_t allowed=sweep(world,ax,ay,az,tx,y,z,cfg->clearance);
        if (allowed>best) { best=allowed; selected=(int32_t)i; }
        if ((fixed_mul(cfg->distance,allowed)>>8)>=cfg->min_distance) { selected=(int32_t)i; best=allowed; break; }
    }
    // Collision response is immediate. Return to a shallower pitch gradually.
    int32_t tested_pitch=selected;
    if (selected<c->pitch) selected=c->pitch-1;
    c->pitch=selected;
    int32_t cosine=cfg->pitches[selected][0],sine=cfg->pitches[selected][1];
    int32_t ey=ty+(fixed_mul(cfg->distance,sine)>>8);
    int32_t ez=tz-(fixed_mul(cfg->distance,cosine)>>8);
    if (selected!=tested_pitch) best=sweep(world,ax,ay,az,tx,ey,ez,cfg->clearance);
    if (best<c->fraction) c->fraction=best;
    else { c->fraction+=cfg->recovery_step; if (c->fraction>best) c->fraction=best; }
    c->obstructed=(uint32_t)(c->fraction<256 || c->pitch!=0 || target<256);
    c->eye_x=ax+(fixed_mul(tx-ax,c->fraction)>>8);
    c->eye_y=ay+(fixed_mul(ey-ay,c->fraction)>>8);
    c->eye_z=az+(fixed_mul(ez-az,c->fraction)>>8);
    c->view[0]=256; c->view[1]=0; c->view[2]=0; c->view[3]=(int16_t)-c->eye_x;
    c->view[4]=0; c->view[5]=(int16_t)cosine; c->view[6]=(int16_t)sine;
    c->view[7]=(int16_t)-((fixed_mul(cosine,c->eye_y)+fixed_mul(sine,c->eye_z))>>8);
    c->view[8]=0; c->view[9]=(int16_t)-sine; c->view[10]=(int16_t)cosine;
    c->view[11]=(int16_t)-((fixed_mul(-sine,c->eye_y)+fixed_mul(cosine,c->eye_z))>>8);
}
void camera_reset(camera_t *c, const player_t *p, const camera_config_t *cfg, const camera_world_t *world) {
    c->target_x=p->x; c->target_y=p->y+cfg->target_height; c->target_z=p->z;
    c->look_x=0; c->look_z=0;
    c->previous_x=p->x; c->previous_y=p->y; c->previous_z=p->z;
    c->fraction=256; c->pitch=0; c->respawns=p->respawns;
    frame(c,p,cfg,world);
}
void camera_step(camera_t *c, const player_t *p, const camera_config_t *cfg, const camera_world_t *world) {
    int32_t dx=p->x-c->previous_x,dy=p->y-c->previous_y,dz=p->z-c->previous_z;
    if (p->respawns!=c->respawns || magnitude(dx)>cfg->snap_distance ||
        magnitude(dz)>cfg->snap_distance || magnitude(dy)>cfg->snap_distance) {
        camera_reset(c,p,cfg,world); return;
    }
    c->look_x=filter(c->look_x,clamp(fixed_mul(dx,cfg->lookahead_ticks),cfg->lookahead_limit),cfg->look_shift);
    c->look_z=filter(c->look_z,clamp(fixed_mul(dz,cfg->lookahead_ticks),cfg->lookahead_limit),cfg->look_shift);
    c->target_x=filter(c->target_x,p->x+c->look_x,cfg->follow_shift);
    c->target_z=filter(c->target_z,p->z+c->look_z,cfg->follow_shift);
    int32_t wanted=p->y+cfg->target_height;
    c->target_y=filter(c->target_y,wanted,p->grounded?cfg->vertical_shift:cfg->air_shift);
    c->target_y=wanted+clamp(c->target_y-wanted,cfg->max_vertical_lag);
    c->previous_x=p->x; c->previous_y=p->y; c->previous_z=p->z;
    frame(c,p,cfg,world);
}
