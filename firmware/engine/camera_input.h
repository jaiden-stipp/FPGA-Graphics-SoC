#ifndef ENGINE_CAMERA_INPUT_H
#define ENGINE_CAMERA_INPUT_H
#include "engine_slice.h"
typedef struct {uint32_t seen,yaw,previous;int32_t pitch,dx,dy;} engine_camera_input_t;
static inline uint32_t engine_input_buttons(uint32_t buttons){
    // GPU-positive-forward view also reverses SDK screen X. Reflect the stick
    // X so WASD stays relative to this actual rendered view.
    return (buttons&~3u)|((buttons&1u)<<1)|((buttons&2u)>>1);
}
static inline uint32_t engine_input_look(engine_camera_input_t *s,uint32_t yaw,int32_t pitch){
    if(s->seen){s->dx+=(((int32_t)yaw-(int32_t)s->yaw+128)&255)-128;s->dy+=pitch-s->pitch;}
    s->seen=1;s->yaw=yaw;s->pitch=pitch;
    // Original C-buttons use pressed edges. Release between queued pulses so
    // fast mouse motion cannot silently consume a second event as a held key.
    if(s->previous){s->previous=0;return 0;}
    uint32_t keys=0;
    if(s->dx>=32){keys|=ENGINE_CAMERA_LEFT;s->dx-=32;}
    else if(s->dx<=-32){keys|=ENGINE_CAMERA_RIGHT;s->dx+=32;}
    // The sender increases pitch when the mouse moves upward.
    if(s->dy>=16){keys|=ENGINE_CAMERA_UP;s->dy-=16;}
    else if(s->dy<=-16){keys|=ENGINE_CAMERA_DOWN;s->dy+=16;}
    s->previous=keys;return keys;
}
#endif
