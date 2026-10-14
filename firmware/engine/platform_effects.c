// Explicit boundary for effects/services omitted by the grounds engine slice.
#include "sm64.h"
#include "audio/external.h"
#include "game/sound_init.h"
#include "game/camera.h"
#include "game/interaction.h"
#include "game/level_update.h"
#include "game/object_list_processor.h"
#include "game/game_init.h"
#include "game/main.h"
#include "game/save_file.h"
#include "game/print.h"
#include "game/ingame_menu.h"
#include "game/object_helpers.h"
#include "game/obj_behaviors.h"
#include "behavior_data.h"
#include "respawn.inc"
struct NumTimesCalled gNumCalls;
#ifdef _WIN32
int _fltused;
#endif
u32 gGlobalTimer,gAudioRandom;
u8 gSpecialTripleJump;
s8 gShowDebugText;
struct Object *gCurrentObject;
s32 gNumFindFloorMisses;
s16 gCameraMovementFlags;
s16 engine_warp_timer;
Vec3f gGlobalSoundSource;
s8 gDebugLevelSelect;
struct HudDisplay gHudDisplay;
s16 gCurrAreaIndex=1;
// Identity-only tokens for original comparisons. No behavior interpreter or
// actor is instantiated in this movement milestone.
const BehaviorScript bhvKoopaShellUnderwater[]={0};
const BehaviorScript bhvCarrySomething4[]={0};
const BehaviorScript bhvCarrySomething3[]={0};
const BehaviorScript bhvBowser[]={0};
void engine_unsupported(u32 code);
void play_sound(s32 soundBits,f32 *pos){(void)soundBits;(void)pos;}
void stop_sound(u32 soundBits,f32 *pos){(void)soundBits;(void)pos;}
void set_sound_moving_speed(u8 bank,u8 speed){(void)bank;(void)speed;}
void lower_background_noise(s32 value){(void)value;}
void raise_background_noise(s32 value){(void)value;}
void set_camera_shake_from_hit(s16 shake){(void)shake;}
void set_camera_mode(struct Camera *c,s16 mode,s16 frames){(void)frames;c->mode=mode;}
void print_text_fmt_int(s32 x,s32 y,const char *str,s32 n){(void)x;(void)y;(void)str;(void)n;}
void stop_shell_music(void){}
void load_level_init_text(u32 arg){(void)arg;}
u16 level_control_timer(s32 op){(void)op;engine_unsupported(0x105);return 0;}
void spawn_default_star(f32 x,f32 y,f32 z){(void)x;(void)y;(void)z;engine_unsupported(0x106);}
void obj_set_held_state(struct Object *obj,const BehaviorScript *behavior){(void)obj;(void)behavior;engine_unsupported(0x107);}
void *virtual_to_segmented(u32 segment,const void *address){(void)segment;return (void *)address;}
s16 level_trigger_warp(struct MarioState *m,s32 op){
    if(op!=WARP_OP_DEATH && op!=WARP_OP_WARP_FLOOR){engine_unsupported(0x103);return 0;}
    // Timers are the unchanged death/floor values in level_update.c. Grounds
    // recovery maps the destination to its spawn; no save/game-over engine yet.
    if(!engine_warp_timer){engine_warp_timer=op==WARP_OP_DEATH?ENGINE_DEATH_DELAY:ENGINE_WARP_FLOOR_DELAY;m->invincTimer=-1;}
    return engine_warp_timer;
}
