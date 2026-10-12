#ifndef RENDER_INTERPOLATION_H
#define RENDER_INTERPOLATION_H
#include "player.h"
#include "game_clock.h"
// Presentation-only interpolation. No division helpers, MULH or 64-bit math.
static inline int32_t game_render_lerp(int32_t a,int32_t b,uint32_t alpha) {
    if(alpha>=65536u)return b;
    int32_t delta=b-a;
    return a+fixed_mul(delta>>16,(int32_t)alpha)+
        (int32_t)((uint32_t)fixed_mul((int32_t)((uint32_t)delta&65535u),(int32_t)alpha)>>16);
}
static inline uint32_t game_render_fraction(const game_runtime_clock_t *clock,uint32_t now) {
    uint32_t n=now-clock->previous,d=clock->period,q=0;
    if(n>=d)return 65536u;
    for(uint32_t i=0;i<16;++i) {
        q<<=1;
        if(n>=d-n){n-=d-n;q|=1u;}else n<<=1;
    }
    return q;
}
#endif
