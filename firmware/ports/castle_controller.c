// Scoped integer lowering of SM64 walking/sliding speed rules. This is not
// mario_step.c: shared capsule collision still supplies the movement outcome.
// Source identities and coefficients are checked by sm64_gameplay.py.
#include "castle_gameplay.h"
#include "castle_surface_types.h"
#include "castle_gameplay_data.h"
static int32_t abs32(int32_t x) {return x<0?-x:x;}
static uint32_t divide(uint32_t a,uint32_t b) {
    uint32_t q=0,r=0;
    for(uint32_t i=32;i;--i){r=(r<<1)|((a>>(i-1))&1u);if(r>=b){r-=b;q|=1u<<(i-1);}}
    return q;
}
static int32_t divs(int32_t a,int32_t b) {return a<0?-(int32_t)divide((uint32_t)-a,(uint32_t)b):(int32_t)divide((uint32_t)a,(uint32_t)b);}
static uint32_t root(uint32_t x) {
    uint32_t q=0,bit=1u<<30;
    while(bit>x)bit>>=2;
    while(bit){if(x>=q+bit){x-=q+bit;q=(q>>1)+bit;}else q>>=1;bit>>=2;}
    return q;
}
static uint32_t floor_class(uint16_t type,uint32_t slide) {
    switch(type) {
    case CASTLE_SURFACE_NOT_SLIPPERY:case CASTLE_SURFACE_HARD_NOT_SLIPPERY:case CASTLE_SURFACE_SWITCH:return 3;
    case CASTLE_SURFACE_SLIPPERY:case CASTLE_SURFACE_NOISE_SLIPPERY:case CASTLE_SURFACE_HARD_SLIPPERY:case CASTLE_SURFACE_NO_CAM_COL_SLIPPERY:return 1;
    case CASTLE_SURFACE_VERY_SLIPPERY:case CASTLE_SURFACE_ICE:case CASTLE_SURFACE_HARD_VERY_SLIPPERY:
    case CASTLE_SURFACE_NOISE_VERY_SLIPPERY_73:case CASTLE_SURFACE_NOISE_VERY_SLIPPERY_74:
    case CASTLE_SURFACE_NOISE_VERY_SLIPPERY:case CASTLE_SURFACE_NO_CAM_COL_VERY_SLIPPERY:return 2;
    default:return slide?2u:0u;
    }
}
void castle_controller_reset(castle_controller_t *s,const player_t *p) {
    s->speed=s->vx=s->vz=s->remainder_x=s->remainder_z=0;
    s->yaw=(p->facing<<3)&255u;s->action=CASTLE_ACTION_IDLE;s->previous_buttons=0;
}
static void cap_velocity(castle_controller_t *s) {
    uint32_t length=root((uint32_t)(fixed_mul(s->vx,s->vx)+fixed_mul(s->vz,s->vz)));
    if(length>25600u){s->vx=divs(fixed_mul(s->vx,25600),(int32_t)length);s->vz=divs(fixed_mul(s->vz,25600),(int32_t)length);}
}
void castle_controller_step(castle_controller_t *s,player_t *p,const world_area_t *a,uint32_t slide_terrain,uint32_t keys,uint32_t buttons,uint32_t intended_yaw) {
    if((keys&PLAYER_RESET)==PLAYER_RESET){player_step_motion(p,a->physics,keys,0,0);castle_controller_reset(s,p);return;}
    world_contact_t c;int contact=world_floor_contact(a,p,&c);
    uint32_t cls=floor_class(contact && c.surface?c.surface->type:0,slide_terrain);
    int32_t ix=(keys&3u)==PLAYER_RIGHT?1:(keys&3u)==PLAYER_LEFT?-1:0;
    int32_t iz=(keys&12u)==PLAYER_FORWARD?1:(keys&12u)==PLAYER_BACK?-1:0;
    uint32_t target=intended_yaw&255u;
    int moving=ix || iz;
    int slope=contact && c.normal && c.normal[1]<(slide_terrain?4095:3956);
    if(p->grounded && slope && cls!=3u) {
        if(s->action!=CASTLE_ACTION_SLIDE){s->vx=fixed_mul(s->speed,castle_game_rotations[s->yaw][1])>>8;s->vz=fixed_mul(s->speed,castle_game_rotations[s->yaw][0])>>8;}
        s->action=CASTLE_ACTION_SLIDE;
    }
    if(p->grounded && s->action==CASTLE_ACTION_SLIDE) {
        int32_t accel=cls==2u?10:cls==1u?8:cls==3u?5:7;
        // Original steering uses the newly updated X velocity for Z, then
        // restores old speed before adding slope acceleration and friction.
        uint32_t old=root((uint32_t)(fixed_mul(s->vx,s->vx)+fixed_mul(s->vz,s->vz)));
        int32_t steer=moving?castle_game_rotations[(target-s->yaw)&255u][1]:0;
        s->vx+=divs(fixed_mul(s->vz,steer)>>8,20);
        s->vz-=divs(fixed_mul(s->vx,steer)>>8,20);
        uint32_t now=root((uint32_t)(fixed_mul(s->vx,s->vx)+fixed_mul(s->vz,s->vz)));
        if(old && now){s->vx=divs(fixed_mul(s->vx,(int32_t)old),(int32_t)now);s->vz=divs(fixed_mul(s->vz,(int32_t)old),(int32_t)now);}
        if(c.normal){s->vx+=(fixed_mul(c.normal[0],accel*256)>>12);s->vz+=(fixed_mul(c.normal[2],accel*256)>>12);}
        int32_t forward=moving?castle_game_rotations[(target-s->yaw)&255u][0]:0;
        int32_t loss=(cls==2u?251:cls==1u?246:236)+((forward*5)>>8);
        s->vx=fixed_mul(s->vx,loss)>>8;s->vz=fixed_mul(s->vz,loss)>>8;cap_velocity(s);
        s->speed=(int32_t)root((uint32_t)(fixed_mul(s->vx,s->vx)+fixed_mul(s->vz,s->vz)));
        uint32_t best=0;int32_t dot=-2147483647;
        for(uint32_t i=0;i<256;i+=8){int32_t d=fixed_mul(s->vx,castle_game_rotations[i][1])+fixed_mul(s->vz,castle_game_rotations[i][0]);if(d>dot){dot=d;best=i;}}
        if(s->vx || s->vz)s->yaw=best;
        if(!slope && abs32(s->vx)+abs32(s->vz)<1024){s->action=CASTLE_ACTION_IDLE;s->speed=s->vx=s->vz=0;}
    }else if(p->grounded) {
        int32_t target_speed=moving?(contact && c.surface && c.surface->type==CASTLE_SURFACE_SLOW?24:32)*256:0;
        if(!moving){s->speed-=512;if(s->speed<0)s->speed=0;}
        else if(s->speed<=0)s->speed+=282;
        else if(s->speed<target_speed)s->speed+=282-divs(s->speed,43);
        else s->speed-=256;
        if(s->speed>12288)s->speed=12288;
        if(moving){int32_t d=(int32_t)((target-s->yaw+128u)&255u)-128;if(d>8)d=8;if(d< -8)d=-8;s->yaw=(s->yaw+(uint32_t)d)&255u;}
        s->vx=fixed_mul(s->speed,castle_game_rotations[s->yaw][1])>>8;
        s->vz=fixed_mul(s->speed,castle_game_rotations[s->yaw][0])>>8;
        if(p->grounded)s->action=moving?CASTLE_ACTION_WALK:CASTLE_ACTION_IDLE;
    }else if(s->action!=CASTLE_ACTION_GROUND_POUND) {
        // mario_actions_airborne.c update_air_without_turn: approach zero
        // by .35, analog forward acceleration 1.5 and sideways speed 10.
        if(s->speed>0){s->speed-=90;if(s->speed<0)s->speed=0;}
        else if(s->speed<0){s->speed+=90;if(s->speed>0)s->speed=0;}
        int32_t sideways=0;
        if(moving){uint32_t dyaw=(target-s->yaw)&255u;s->speed+=(fixed_mul(castle_game_rotations[dyaw][0],384)>>8);sideways=castle_game_rotations[dyaw][1]*10;}
        if(s->speed>8192)s->speed-=256;if(s->speed< -4096)s->speed+=512;
        int32_t co=castle_game_rotations[s->yaw][0],si=castle_game_rotations[s->yaw][1];
        s->vx=(fixed_mul(s->speed,si)+fixed_mul(sideways,co))>>8;
        s->vz=(fixed_mul(s->speed,co)-fixed_mul(sideways,si))>>8;cap_velocity(s);
    }
    if(!p->grounded && (buttons&GAME_USE) && !(s->previous_buttons&GAME_USE)){s->action=CASTLE_ACTION_GROUND_POUND;s->vx=s->vz=0;p->velocity_y=-50;}
    s->remainder_x+=s->vx;s->remainder_z+=s->vz;
    int32_t dx=s->remainder_x/256,dz=s->remainder_z/256;
    s->remainder_x-=dx*256;s->remainder_z-=dz*256;
    int32_t limit=a->physics->radius/2;if(limit>8)limit=8;
    while(dx || dz){int32_t x=dx>limit?limit:dx< -limit?-limit:dx,z=dz>limit?limit:dz< -limit?-limit:dz;
        world_collision(a,p);player_move_horizontal(p,a->physics,x,z);dx-=x;dz-=z;}
    world_collision(a,p);uint32_t respawns=p->respawns;
    player_step_motion(p,a->physics,keys,0,0);
    if(p->respawns!=respawns)castle_controller_reset(s,p);
    if(!p->grounded && s->action!=CASTLE_ACTION_GROUND_POUND)s->action=CASTLE_ACTION_AIR;
    p->facing=((s->yaw+4u)>>3)&31u;s->previous_buttons=buttons;
}
