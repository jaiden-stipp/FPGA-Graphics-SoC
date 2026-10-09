#include "first_person.h"
static void view(first_person_t *camera, const player_t *p, const first_person_config_t *c) {
    int32_t cosine=c->rotations[camera->yaw][0], sine=c->rotations[camera->yaw][1];
    int16_t *m=camera->view;
    m[0]=(int16_t)cosine; m[1]=0; m[2]=(int16_t)-sine;
    m[3]=(int16_t)-((fixed_mul(cosine,p->x)-fixed_mul(sine,p->z))>>8);
    m[4]=0; m[5]=256; m[6]=0; m[7]=(int16_t)-(p->y+c->eye_height);
    m[8]=(int16_t)sine; m[9]=0; m[10]=(int16_t)cosine;
    m[11]=(int16_t)-((fixed_mul(sine,p->x)+fixed_mul(cosine,p->z))>>8);
}
void first_person_reset(first_person_t *camera, const player_t *p, const first_person_config_t *c) {
    camera->yaw=c->initial_yaw; camera->respawns=p->respawns; view(camera,p,c);
}
void first_person_step(first_person_t *camera, player_t *p, const player_world_t *world,
                       const first_person_config_t *c, uint32_t keys) {
    static const uint8_t directions[8]={4,6,2,10,8,9,1,5};
    uint32_t movement=keys&PLAYER_JUMP;
    if ((keys&PLAYER_RESET)==PLAYER_RESET) movement=keys;
    else {
        if ((keys&3u)==PLAYER_LEFT) camera->yaw=(camera->yaw+63u)&63u;
        if ((keys&3u)==PLAYER_RIGHT) camera->yaw=(camera->yaw+1u)&63u;
        uint32_t heading=((camera->yaw+4u)>>3)&7u;
        if ((keys&12u)==PLAYER_BACK) heading=(heading+4u)&7u;
        if ((keys&12u)==PLAYER_FORWARD || (keys&12u)==PLAYER_BACK) movement|=directions[heading];
    }
    player_step(p,world,movement);
    if (p->x < -c->region_radius || p->x>c->region_radius ||
        p->z < -c->region_radius || p->z>c->region_radius) { player_reset(p,world); ++p->respawns; }
    if (camera->respawns!=p->respawns) { first_person_reset(camera,p,c); return; }
    view(camera,p,c);
}
