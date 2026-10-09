#include "castle_rules.h"
#include "castle_surface_types.h"

// Scoped port of interaction.c mario_handle_special_floors/check_death_barrier.
// Original death/vertical-wind floors trigger WARP_OP_WARP_FLOOR (node F3),
// not the health-death node F1. Sound, fade and lives are not implemented here.
uint32_t castle_floor_event(uint16_t type,int32_t player_y,int32_t floor_y) {
    if(type==CASTLE_SURFACE_DEATH_PLANE || type==CASTLE_SURFACE_VERTICAL_WIND)
        return player_y<floor_y+2048?0xF3u:0;
    if(type==CASTLE_SURFACE_WARP)return 0xF3u;
    return 0;
}
