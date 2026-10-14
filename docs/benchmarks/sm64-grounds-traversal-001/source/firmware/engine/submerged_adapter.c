// Include the unchanged upstream unit to reach its private swimming handlers.
#include "src/game/mario_actions_submerged.c"
void engine_unsupported(u32 code);
void engine_reset_swimming(void) {
    sWasAtSurface=FALSE;sSwimStrength=MIN_SWIM_STRENGTH;
    sBobTimer=sBobIncrement=0;sBobHeight=0.0f;
}
s32 engine_submerged_action(struct MarioState *m) {
    if(check_common_submerged_cancels(m))return TRUE;
    m->quicksandDepth=0.0f;
    m->marioBodyState->headAngle[1]=m->marioBodyState->headAngle[2]=0;
    switch(m->action) {
    case ACT_WATER_IDLE:return act_water_idle(m);
    case ACT_WATER_ACTION_END:return act_water_action_end(m);
    case ACT_WATER_PLUNGE:return act_water_plunge(m);
    case ACT_BREASTSTROKE:return act_breaststroke(m);
    case ACT_SWIMMING_END:return act_swimming_end(m);
    case ACT_FLUTTER_KICK:return act_flutter_kick(m);
    case ACT_DROWNING:return act_drowning(m);
    case ACT_WATER_DEATH:return act_water_death(m);
    case ACT_BACKWARD_WATER_KB:return act_backward_water_kb(m);
    case ACT_FORWARD_WATER_KB:return act_forward_water_kb(m);
    default:engine_unsupported(m->action);return FALSE;
    }
}
