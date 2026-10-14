// Castle traversal foundation. Original actor/terrain/collision data; scoped
// walking controller. Original SM64 slide actions and mission are not yet ported.
#include "soc.h"
#include "cpu_profile.h"
#include "gfx.h"
#include "game_port.h"
#include "game_services.h"
#include "world_data.h"
#include "castle_actor_data.h"
#include "castle_transitions.h"
#include "castle_rules.h"
#include "render_interpolation.h"
#ifdef CASTLE_ENGINE_SLICE
#include "../engine/engine_slice.h"
#include "spawn.inc"
volatile uint32_t castle_engine_fault;
volatile uint32_t castle_engine_state[4]; // action, health, water level, warp timer
volatile uint32_t castle_engine_visual[4]; // animation, frame, camera mode, camera yaw
volatile int16_t castle_engine_view[12];
volatile uint32_t castle_engine_pose_cycles,castle_engine_camera_cycles;
static uint32_t castle_engine_respawn_seen;
static uint32_t engine_look_seen,engine_look_yaw;
static int32_t engine_look_pitch,engine_look_dx,engine_look_dy;
#endif
#ifdef CASTLE_GAMEPLAY
#include "castle_gameplay.h"
static castle_controller_t controller;
#endif
static player_t player;
static animation_t animation;
#ifndef CASTLE_ENGINE_SLICE
static animation_matrix_t joints[GAME_ANIMATION_JOINTS];
#endif
static scene_vertex_t posed[GAME_ANIMATION_VERTICES];
static scene_vertex_t pose_previous[GAME_ANIMATION_VERTICES],pose_current[GAME_ANIMATION_VERTICES];
static player_t render_previous_player;
static game_view_t render_previous_view;
static game_view_t view;
static camera_orbit_t camera;
// Original radial/8-direction camera uses a 1000-unit base distance and
// 125-unit eye focus. Interiors use a shorter boom to fit their rooms.
#ifndef CASTLE_ENGINE_SLICE
static const camera_orbit_config_t outdoor_camera={1000,125,20,1000,2,3,16};
static const camera_orbit_config_t indoor_camera={800,125,20,1000,2,3,16};
#endif
#define CASTLE_DEFAULT_PITCH (-16)
static uint32_t current_area,previous_buttons,transition_cooldown;
static uint32_t pending_event,pending_ticks;
static void render_capture(uint32_t reset_history) {
#ifdef CASTLE_ENGINE_SLICE
    uint32_t pose_cycles=SOC_CYCLES;
    DETAIL_START(pose_start);
    if(sm64_engine_pose((int16_t *)pose_current,GAME_ANIMATION_VERTICES,4))castle_engine_fault=0x204;
    castle_engine_pose_cycles=SOC_CYCLES-pose_cycles;
    for(uint32_t k=0;k<4;++k)castle_engine_visual[k]=sm64_engine_visual_probe(k);
    DETAIL_END(PROFILE_ANIMATION_STEP,pose_start);
#else
    animation_pose(&animation,&game_animation_package,joints,pose_current);
#endif
    for(uint32_t i=0;i<GAME_ANIMATION_VERTICES;++i) {
#ifndef CASTLE_ENGINE_SLICE
        pose_current[i].x=(int16_t)(pose_current[i].x*4);
        pose_current[i].y=(int16_t)(pose_current[i].y*4);
        pose_current[i].z=(int16_t)(pose_current[i].z*4);
#endif
        if(reset_history)pose_previous[i]=pose_current[i];
    }
    if(reset_history){render_previous_player=player;render_previous_view=view;}
}
volatile player_t game_player;
volatile uint32_t castle_area,castle_mission_state;
volatile uint32_t castle_exit_event;
volatile uint32_t castle_pose_upload_cycles,castle_prepare_cycles,castle_draw_cycles;
static void camera_update(void) {
    DETAIL_START(camera_start);
#ifdef CASTLE_ENGINE_SLICE
    uint32_t camera_cycles=SOC_CYCLES;
    sm64_engine_camera_step(view.view,4);
    castle_engine_camera_cycles=SOC_CYCLES-camera_cycles;
    for(uint32_t k=0;k<12;++k)castle_engine_view[k]=view.view[k];
    if(sm64_engine_probe(0))castle_engine_fault=sm64_engine_probe(0);
#else
    player_t origin={0};
    game_view_update(&view,&origin,0,castle_rotations);
    camera_world_t cw={world_areas[current_area].camera_surfaces,world_areas[current_area].camera_count};
    const camera_orbit_config_t *cfg=current_area>=1 && current_area<=3?&indoor_camera:&outdoor_camera;
    camera_orbit_step(&camera,&player,cfg,&cw,view.view,4);
#endif
    DETAIL_END(PROFILE_CAMERA,camera_start);
}
#ifndef CASTLE_ENGINE_SLICE
static void enter_area(uint32_t area,const int16_t arrival[3],uint8_t yaw) {
    current_area=area;world_select(world_areas+area,&player);
    player.x=arrival[0];player.y=arrival[1];player.z=arrival[2];player.grounded=0;
    view.yaw=yaw;view.pitch=CASTLE_DEFAULT_PITCH;camera.initialized=0;
    transition_cooldown=15;pending_event=pending_ticks=0;
    world_collision(world_areas+area,&player);
    animation_reset(&animation,&player,&game_animation_package);
#ifdef CASTLE_GAMEPLAY
    castle_controller_reset(&controller,&player);castle_gameplay_enter(area);
#endif
}
#endif
int game_port_init(void) {
    current_area=previous_buttons=transition_cooldown=0;view.yaw=128;view.pitch=CASTLE_DEFAULT_PITCH;
    camera.initialized=0;
    pending_event=pending_ticks=castle_exit_event=0;
    world_select(world_areas,&player);
    animation_reset(&animation,&player,&game_animation_package);
#ifdef CASTLE_GAMEPLAY
    castle_gameplay_init();castle_controller_reset(&controller,&player);
#endif
#ifdef CASTLE_ENGINE_SLICE
    int32_t engine_spawn[3]={player.x,player.y,player.z};
    sm64_engine_init_heading(engine_spawn,ENGINE_GROUNDS_SPAWN_YAW);castle_engine_fault=sm64_engine_probe(0);
    castle_engine_respawn_seen=0;
    engine_look_seen=0;engine_look_dx=engine_look_dy=0;
#endif
    castle_mission_state=0;camera_update();render_capture(1);return 0;
}
void game_port_update(uint32_t word) {
    uint32_t old_area=current_area,old_respawns=player.respawns;
    render_previous_player=player;render_previous_view=view;
    for(uint32_t i=0;i<GAME_ANIMATION_VERTICES;++i)pose_previous[i]=pose_current[i];
    game_input_t input;game_input_decode(&input,word);
    if(input.has_look) {
#ifndef CASTLE_ENGINE_SLICE
        view.yaw=input.yaw;view.pitch=CASTLE_DEFAULT_PITCH+input.pitch;
        if(view.pitch< -32)view.pitch=-32;if(view.pitch>0)view.pitch=0;
#endif
    }
    world_collision(world_areas+current_area,&player);
#ifdef CASTLE_ENGINE_SLICE
    if((input.buttons&GAME_RESET) && !(previous_buttons&GAME_RESET)) {
        const player_world_t *physics=world_areas[0].physics;
        int32_t engine_spawn[3]={physics->spawn_x,physics->spawn_y,physics->spawn_z};
        sm64_engine_init_heading(engine_spawn,ENGINE_GROUNDS_SPAWN_YAW);++player.respawns;camera.initialized=0;
        castle_engine_respawn_seen=0;
        engine_look_seen=0;engine_look_dx=engine_look_dy=0;
    }
    // The current renderer's yaw points forward; the original camera yaw
    // describes the opposite direction. Reflect the stick X axis as well.
    uint32_t engine_buttons=(input.buttons&~3u)|((input.buttons&1u)<<1)|((input.buttons&2u)>>1);
    // Convert mouse deltas to original C-button events without forcing Lakitu
    // to an absolute orbit. The first packet establishes an input reference.
    if(input.has_look){
        if(engine_look_seen){engine_look_dx+=(((int32_t)input.yaw-(int32_t)engine_look_yaw+128)&255)-128;
            engine_look_dy+=input.pitch-engine_look_pitch;}
        engine_look_yaw=input.yaw;engine_look_pitch=input.pitch;engine_look_seen=1;
        if(engine_look_dx>=32){engine_buttons|=ENGINE_CAMERA_RIGHT;engine_look_dx-=32;}
        else if(engine_look_dx<=-32){engine_buttons|=ENGINE_CAMERA_LEFT;engine_look_dx+=32;}
        if(engine_look_dy>=16){engine_buttons|=ENGINE_CAMERA_DOWN;engine_look_dy-=16;}
        else if(engine_look_dy<=-16){engine_buttons|=ENGINE_CAMERA_UP;engine_look_dy+=16;}
    }
    engine_result_t engine_state;sm64_engine_update(engine_buttons,ENGINE_USE_CAMERA_YAW,&engine_state);
    castle_engine_fault=engine_state.fault;
    castle_engine_state[0]=engine_state.action;
    castle_engine_state[1]=sm64_engine_probe(9);
    castle_engine_state[2]=sm64_engine_probe(10);
    castle_engine_state[3]=sm64_engine_probe(11);
    uint32_t engine_respawns=sm64_engine_probe(8);
    if(engine_respawns!=castle_engine_respawn_seen){player.respawns+=engine_respawns-castle_engine_respawn_seen;castle_engine_respawn_seen=engine_respawns;camera.initialized=0;}
    player.x=engine_state.x;player.y=engine_state.y;player.z=engine_state.z;
    player.velocity_y=engine_state.velocity_y;player.grounded=engine_state.grounded;player.facing=engine_state.facing;
    controller.action=player.grounded?(input.buttons&15u?CASTLE_ACTION_WALK:CASTLE_ACTION_IDLE):CASTLE_ACTION_AIR;
#elif defined(CASTLE_GAMEPLAY)
    if(!pending_ticks && !castle_gameplay_frozen())castle_controller_step(&controller,&player,world_areas+current_area,current_area==4,game_movement_keys(&input,view.yaw),input.buttons,game_movement_heading(&input,view.yaw));
    if(player.respawns!=old_respawns){castle_controller_reset(&controller,&player);castle_gameplay_enter(current_area);}
    uint32_t mission_event=castle_gameplay_step(&player,current_area,input.buttons,controller.action);
    castle_mission_state=castle_gameplay_mission();
    if(mission_event && !pending_ticks){pending_event=castle_exit_event=mission_event;pending_ticks=20;}
#else
    player_step(&player,world_areas[current_area].physics,game_movement_keys(&input,view.yaw));
#endif
#ifndef CASTLE_ENGINE_SLICE
    if(pending_ticks) {
        if(!--pending_ticks) {
            const world_exit_t *exit=world_exit_find(castle_exits,CASTLE_EXIT_COUNT,current_area,pending_event);
            if(exit)enter_area(exit->destination_area,exit->arrival,exit->yaw);
            else pending_event=0;
        }
    }else if(transition_cooldown)--transition_cooldown;
    else {
        world_contact_t contact;
        if(world_floor_contact(world_areas+current_area,&player,&contact) && contact.surface) {
            uint32_t event=castle_floor_event(contact.surface->type,player.y,contact.height);
            if(event) {
                // level_update.c falls back to F1 when the area has no F3.
                const world_exit_t *exit=world_exit_find(castle_exits,CASTLE_EXIT_COUNT,current_area,event);
                if(!exit) {event=CASTLE_EXIT_DEATH;exit=world_exit_find(castle_exits,CASTLE_EXIT_COUNT,current_area,event);}
                if(exit) {pending_event=castle_exit_event=event;pending_ticks=20;}
            }
        }
        int32_t i=world_transition_find(castle_transitions,CASTLE_TRANSITION_COUNT,current_area,&player,
            (input.buttons&GAME_USE)&&!(previous_buttons&GAME_USE),
#ifdef CASTLE_GAMEPLAY
            castle_gameplay_stars(),castle_gameplay_keys());
#else
            70,3);
#endif
        if(i>=0 && !pending_event) {
            const world_transition_t *t=castle_transitions+i;
            enter_area(t->destination_area,t->arrival,t->yaw);
        }
    }
#endif
    previous_buttons=input.buttons;
#ifndef CASTLE_ENGINE_SLICE
    DETAIL_START(animation_start);
#ifdef CASTLE_GAMEPLAY
    if(controller.action==CASTLE_ACTION_SLIDE)animation_step_clip(&animation,&player,&game_animation_package,4,6);
    else if(controller.action==CASTLE_ACTION_GROUND_POUND)animation_step_clip(&animation,&player,&game_animation_package,5,6);
    else
#endif
    animation_step(&animation,&player,&game_animation_package);
    DETAIL_END(PROFILE_ANIMATION_STEP,animation_start);
#ifdef CASTLE_PROFILE_FIXED_POSE
    // Benchmark fixture only: original idle start pose, independent of FPS.
    animation.clip=ANIMATION_IDLE;
    animation.phase=(uint32_t)game_animation_package.clips[ANIMATION_IDLE].start<<8;
#endif
#endif
    camera_update();
    render_capture(old_area!=current_area || old_respawns!=player.respawns);
    game_player.x=player.x;game_player.y=player.y;game_player.z=player.z;
    game_player.grounded=player.grounded;game_player.velocity_y=player.velocity_y;
    game_player.facing=player.facing;game_player.previous_keys=player.previous_keys;game_player.respawns=player.respawns;
    castle_area=current_area;
}
static int render_frame(uint32_t frame,uint32_t alpha) {
    // Unsupported engine actions remain latched in castle_engine_fault.
    // Keep rendering/input alive so reset can recover the experimental slice.
    uint32_t start=SOC_CYCLES;
    player_t render_player=player;game_view_t render_view=view;
    render_player.x=game_render_lerp(render_previous_player.x,player.x,alpha);
    render_player.y=game_render_lerp(render_previous_player.y,player.y,alpha);
    render_player.z=game_render_lerp(render_previous_player.z,player.z,alpha);
#ifdef CASTLE_ENGINE_SLICE
    for(uint32_t i=0;i<12;++i)render_view.view[i]=(int16_t)game_render_lerp(render_previous_view.view[i],view.view[i],alpha);
#else
    int32_t yaw=(int32_t)view.yaw,old_yaw=(int32_t)render_previous_view.yaw;
    int32_t yaw_delta=((yaw-old_yaw+128)&255)-128;
    render_view.yaw=(uint32_t)game_render_lerp(old_yaw,old_yaw+yaw_delta,alpha)&255u;
    render_view.pitch=game_render_lerp(render_previous_view.pitch,view.pitch,alpha);
    player_t origin={0};game_view_update(&render_view,&origin,0,castle_rotations);
    for(uint32_t i=3;i<12;i+=4)render_view.view[i]=(int16_t)game_render_lerp(render_previous_view.view[i],view.view[i],alpha);
#endif
    for(uint32_t i=0;i<GAME_ANIMATION_VERTICES;++i) {
        posed[i].x=(int16_t)game_render_lerp(pose_previous[i].x,pose_current[i].x,alpha);
        posed[i].y=(int16_t)game_render_lerp(pose_previous[i].y,pose_current[i].y,alpha);
        posed[i].z=(int16_t)game_render_lerp(pose_previous[i].z,pose_current[i].z,alpha);
    }
    uint32_t offset=0;
    for(uint32_t h=0;h<PORTABLE_MESH_COUNT;++h) {
        if(game_mesh_frame((uint8_t)h,posed+offset,portable_meshes[h].vertex_count))return -1;
        offset+=portable_meshes[h].vertex_count;
    }
    castle_pose_upload_cycles=SOC_CYCLES-start;start=SOC_CYCLES;
    if(world_prepare(world_areas+current_area,&render_player,render_view.view,PORTABLE_MESH_COUNT))return -1;
    castle_prepare_cycles=SOC_CYCLES-start;start=SOC_CYCLES;
    if(gfx_identity_view() || gfx_begin_frame(frame))return -1;
    if(world_draw(world_areas+current_area,&render_player,render_view.view,PORTABLE_MESH_COUNT))return -1;
#ifdef CASTLE_ENGINE_SLICE
    int16_t model[12];for(uint32_t i=0;i<12;++i)model[i]=render_view.view[i];
#else
    int32_t angle=(int32_t)((player.facing<<3)&255),previous=(int32_t)((render_previous_player.facing<<3)&255);
    int32_t delta=((angle-previous+128)&255)-128;
    uint32_t facing=(uint32_t)game_render_lerp(previous,previous+delta,alpha)&255u;
    int32_t co=castle_rotations[facing][0],si=castle_rotations[facing][1];
    int16_t model[12];
    for(uint32_t row=0;row<3;++row) {
        uint32_t b=row<<2;
        model[b]=(int16_t)((fixed_mul(render_view.view[b],co)-fixed_mul(render_view.view[b+2],si))>>8);
        model[b+1]=render_view.view[b+1];
        model[b+2]=(int16_t)((fixed_mul(render_view.view[b],si)+fixed_mul(render_view.view[b+2],co))>>8);
        model[b+3]=render_view.view[b+3];
    }
#endif
    for(uint32_t h=0;h<PORTABLE_MESH_COUNT;++h)if(gfx_draw_matrix((uint8_t)h,model))return -1;
#ifdef CASTLE_GAMEPLAY
    if(castle_gameplay_draw(current_area,&render_player,&render_view))return -1;
#endif
    castle_draw_cycles=SOC_CYCLES-start;
    return gfx_end_frame();
}
int game_port_render(uint32_t frame) { return render_frame(frame,65536u); }
int game_port_render_interpolated(uint32_t frame,uint32_t alpha) { return render_frame(frame,alpha); }
