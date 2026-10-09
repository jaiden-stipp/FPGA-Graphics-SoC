#include "beacon.h"
void beacon_reset(beacon_state_t *s, const player_t *p) {
    s->collected=0; s->score=0; s->ticks=0; s->respawns=p->respawns; s->won=0;
}
void beacon_step(beacon_state_t *s, const player_t *p, const beacon_config_t *c) {
    if (s->respawns!=p->respawns) beacon_reset(s,p);
    if (s->won) return;
    ++s->ticks;
    for (uint32_t i=0; i<c->count; ++i) {
        int32_t dx=p->x-c->positions[i][0], dz=p->z-c->positions[i][2];
        int32_t dy=p->y-c->positions[i][1];
        // Axis rejection bounds products even if a player falls far outside.
        if (!(s->collected&(1u<<i)) && dx>=-c->radius && dx<=c->radius &&
            dz>=-c->radius && dz<=c->radius && dy>=-c->height && dy<=c->height &&
            fixed_mul(dx,dx)+fixed_mul(dz,dz)<=fixed_mul(c->radius,c->radius)) {
            s->collected|=1u<<i; ++s->score;
        }
    }
    s->won=s->score==c->count;
}
