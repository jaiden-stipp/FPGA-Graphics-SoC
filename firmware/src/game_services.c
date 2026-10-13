#include "game_services.h"
#include "gfx.h"
#include "gfx_protocol.h"
#include "soc.h"
void game_input_decode(game_input_t *i,uint32_t word) {
    i->buttons=word&255u;i->yaw=(word>>8)&255u;
    i->pitch=(int8_t)(word>>16);i->has_look=word>>31;
    if(i->pitch>32)i->pitch=32;if(i->pitch< -32)i->pitch= -32;
}
uint32_t game_movement_keys(const game_input_t *i,uint32_t yaw) {
    static const int8_t x[8]={0,1,1,1,0,-1,-1,-1}, z[8]={1,1,0,-1,-1,-1,0,1};
    uint32_t h=((yaw+16u)>>5)&7u;int32_t dx=0,dz=0;
    if(i->buttons&GAME_RESET)return PLAYER_RESET;
    if(i->buttons&4u){dx+=x[h];dz+=z[h];}if(i->buttons&8u){dx-=x[h];dz-=z[h];}
    h=(h+2u)&7u;
    if(i->buttons&2u){dx+=x[h];dz+=z[h];}if(i->buttons&1u){dx-=x[h];dz-=z[h];}
    return (i->buttons&PLAYER_JUMP)|(dx<0?1u:dx>0?2u:0u)|(dz>0?4u:dz<0?8u:0u);
}
void game_view_update(game_view_t *v,const player_t *p,int32_t eye,const int16_t r[256][2]) {
    int32_t cy=r[v->yaw&255u][0],sy=r[v->yaw&255u][1];
    int32_t cp=r[(uint32_t)v->pitch&255u][0],sp=r[(uint32_t)v->pitch&255u][1];
    int16_t *m=v->view;
    m[0]=(int16_t)cy;m[1]=0;m[2]=(int16_t)-sy;
    m[4]=(int16_t)-(fixed_mul(sp,sy)>>8);m[5]=(int16_t)cp;m[6]=(int16_t)-(fixed_mul(sp,cy)>>8);
    m[8]=(int16_t)(fixed_mul(cp,sy)>>8);m[9]=(int16_t)sp;m[10]=(int16_t)(fixed_mul(cp,cy)>>8);
    for(uint32_t row=0;row<3;++row) {
        uint32_t b=row<<2;
        m[b+3]=(int16_t)-((fixed_mul(m[b],p->x)+fixed_mul(m[b+1],p->y+eye)+fixed_mul(m[b+2],p->z))>>8);
    }
}
uint32_t game_movement_heading(const game_input_t *input,uint32_t yaw) {
    int32_t side=((input->buttons&2u)!=0)-((input->buttons&1u)!=0);
    int32_t forward=((input->buttons&4u)!=0)-((input->buttons&8u)!=0);
    uint32_t angle=forward>0?(side>0?32u:side<0?224u:0u):
        forward<0?(side>0?96u:side<0?160u:128u):side>0?64u:192u;
    return (yaw+angle)&255u;
}
int game_object_overlap(const game_object_t *o,const player_t *p,int32_t r,int32_t height) {
    return o->enabled && p->x+r>o->x+o->local.min_x && p->x-r<o->x+o->local.max_x &&
        p->z+r>o->z+o->local.min_z && p->z-r<o->z+o->local.max_z &&
        p->y+height>o->y+o->local.min_y && p->y<o->y+o->local.max_y;
}
void game_door_step(game_object_t *o,int opening,int32_t speed,int32_t travel) {
    o->phase+=opening?speed:-speed;
    if(o->phase<0)o->phase=0;if(o->phase>travel)o->phase=travel;
}
uint32_t game_object_resolve_box(const game_object_t *o,player_t *p,const int32_t previous[3],int32_t r,int32_t h) {
    if(!o->enabled)return 0;
    int32_t left=o->x+o->local.min_x-r,right=o->x+o->local.max_x+r;
    int32_t front=o->z+o->local.min_z-r,back=o->z+o->local.max_z+r;
    int32_t bottom=o->y+o->local.min_y,top=o->y+o->local.max_y;
    if(p->x<=left || p->x>=right || p->z<=front || p->z>=back)return 0;
    if(previous[1]>=top && p->y<=top && p->velocity_y<=0){p->y=top;p->velocity_y=0;p->grounded=1;return 1;}
    if(previous[1]+h<=bottom && p->y+h>=bottom && p->velocity_y>0){p->y=bottom-h;p->velocity_y=0;return 2;}
    if(p->y+h<=bottom || p->y>=top)return 0;
    if(previous[0]<=left)p->x=left;
    else if(previous[0]>=right)p->x=right;
    else if(previous[2]<=front)p->z=front;
    else if(previous[2]>=back)p->z=back;
    else {
        int32_t distance=p->x-left,side=0;
        if(right-p->x<distance){distance=right-p->x;side=1;}
        if(p->z-front<distance){distance=p->z-front;side=2;}
        if(back-p->z<distance)side=3;
        if(side==0)p->x=left;else if(side==1)p->x=right;else if(side==2)p->z=front;else p->z=back;
    }
    return 4;
}
int game_pickup_step(game_object_t *o,const player_t *p,int32_t r,int32_t height) {
    if(!game_object_overlap(o,p,r,height))return 0;
    o->enabled=0;return 1;
}
uint32_t game_animation_frame(uint32_t tick,uint32_t period,uint32_t count) {
    if(!period || !count)return 0;
    // Shift/add division avoids compiler arithmetic helpers on RV32I.
    uint32_t q=0,remainder=0;
    for(uint32_t b=32;b;--b){remainder=(remainder<<1)|((tick>>(b-1))&1u);if(remainder>=period){remainder-=period;q|=1u<<(b-1);}}
    remainder=0;
    for(uint32_t b=32;b;--b){remainder=(remainder<<1)|((q>>(b-1))&1u);if(remainder>=count)remainder-=count;}
    return remainder;
}
static void word(uint8_t *p,int16_t value){p[0]=(uint8_t)((uint16_t)value>>8);p[1]=(uint8_t)value;}
int game_mesh_frame(uint8_t handle,const scene_vertex_t *v,uint32_t count) {
    if(count>128u)return -1;
    for(uint32_t start=0;start<count;) {
        uint32_t n=count-start;if(n>40u)n=40u;
        uint8_t data[243];data[0]=handle;data[1]=(uint8_t)start;data[2]=(uint8_t)n;
        for(uint32_t j=0;j<n;++j){uint32_t b=3u+6u*j;word(data+b,v[start+j].x);word(data+b+2,v[start+j].y);word(data+b+4,v[start+j].z);}
        if(gfx_command(GFX_OP_UPLOAD_VERTICES,data,(uint8_t)(3u+6u*n)))return -1;
        start+=n;
    }
    return 0;
}
static const game_view_t *hud_view;
static int32_t hud_x,hud_y,hud_z,hud_scale;
int game_hud_begin(const game_view_t *view,const player_t *p,int32_t eye,uint32_t focal){
    if(focal<128u || focal>512u)return -1;
    hud_view=view;hud_x=p->x;hud_y=p->y+eye;hud_z=p->z;
    // A camera-attached plane uses existing DRAW_TRIANGLE commands. View and
    // projection cannot change inside an active frame on this GPU.
    uint32_t q=0,remainder=0;
    for(uint32_t b=32;b;--b){remainder=(remainder<<1)|((69632u>>(b-1))&1u);if(remainder>=focal){remainder-=focal;q|=1u<<(b-1);}}
    hud_scale=(int32_t)q;return 0;
}
static void hud_point(uint8_t *out,int16_t x,int16_t y){
    int32_t cx=(fixed_mul(x-160,hud_scale)+128)>>8,cy=(fixed_mul(120-y,hud_scale)+128)>>8;
    const int16_t *m=hud_view->view;
    int32_t wx=hud_x+((fixed_mul(m[0],cx)+fixed_mul(m[4],cy)+fixed_mul(m[8],272)+128)>>8);
    int32_t wy=hud_y+((fixed_mul(m[1],cx)+fixed_mul(m[5],cy)+fixed_mul(m[9],272)+128)>>8);
    int32_t wz=hud_z+((fixed_mul(m[2],cx)+fixed_mul(m[6],cy)+fixed_mul(m[10],272)+128)>>8);
    word(out,(int16_t)wx);word(out+2,(int16_t)wy);word(out+4,(int16_t)wz);
}
static int triangle(int16_t x0,int16_t y0,int16_t x1,int16_t y1,int16_t x2,int16_t y2,uint8_t color) {
    uint8_t data[19];hud_point(data,x0,y0);hud_point(data+6,x1,y1);hud_point(data+12,x2,y2);data[18]=color;
    return gfx_command(GFX_OP_DRAW_TRIANGLE,data,19);
}
int game_hud_rect(int16_t x,int16_t y,int16_t w,int16_t h,uint8_t color) {
    if(w<=0 || h<=0 || x<0 || y<0 || x+w>320 || y+h>240)return -1;
    return triangle(x,y+h,x,y,x+w,y,color) || triangle(x,y+h,x+w,y,x+w,y+h,color);
}
int game_hud_number(int16_t x,int16_t y,uint32_t value,uint32_t digits,uint8_t color) {
    static const uint8_t segments[10]={63,6,91,79,102,109,125,7,127,111};
    if(!digits || digits>3u || value>999u)return -1;
    uint32_t divisor=digits==3u?100u:digits==2u?10u:1u;
    for(uint32_t i=0;i<digits;++i){
        uint32_t digit=0;while(value>=divisor){value-=divisor;++digit;}if(digit>9u)return -1;
        uint8_t s=segments[digit];int16_t left=x+(int16_t)(i*10u);
        if((s&1u)&&game_hud_rect(left+2,y,4,2,color))return -1;
        if((s&2u)&&game_hud_rect(left+6,y+2,2,4,color))return -1;
        if((s&4u)&&game_hud_rect(left+6,y+8,2,4,color))return -1;
        if((s&8u)&&game_hud_rect(left+2,y+12,4,2,color))return -1;
        if((s&16u)&&game_hud_rect(left,y+8,2,4,color))return -1;
        if((s&32u)&&game_hud_rect(left,y+2,2,4,color))return -1;
        if((s&64u)&&game_hud_rect(left+2,y+6,4,2,color))return -1;
        divisor=divisor==100u?10u:1u;
    }
    return 0;
}
