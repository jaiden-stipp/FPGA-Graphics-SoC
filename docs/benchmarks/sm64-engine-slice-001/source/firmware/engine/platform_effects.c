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
void engine_unsupported(u32 code);
void play_sound(s32 soundBits,f32 *pos){(void)soundBits;(void)pos;}
void stop_sound(u32 soundBits,f32 *pos){(void)soundBits;(void)pos;}
void set_sound_moving_speed(u8 bank,u8 speed){(void)bank;(void)speed;}
void lower_background_noise(s32 value){(void)value;}
void raise_background_noise(s32 value){(void)value;}
void set_camera_shake_from_hit(s16 shake){(void)shake;}
void set_camera_mode(struct Camera *c,s16 mode,s16 frames){(void)frames;c->mode=mode;}
void print_text_fmt_int(s32 x,s32 y,const char *str,s32 n){(void)x;(void)y;(void)str;(void)n;}
void mario_drop_held_object(struct MarioState *m){if(m->heldObj)engine_unsupported(0x101);}
void mario_stop_riding_and_holding(struct MarioState *m){if(m->heldObj||m->riddenObj)engine_unsupported(0x102);}
s16 level_trigger_warp(struct MarioState *m,s32 op){(void)m;(void)op;engine_unsupported(0x103);return 0;}
