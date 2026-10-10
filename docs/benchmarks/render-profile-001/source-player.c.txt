#include "player.h"
#define NO_FLOOR (-32768)
static const player_world_t *query_world;
static const uint16_t *query_floors,*query_walls;
static const int16_t (*query_normals)[3];
static uint32_t query_floor_count,query_wall_count;
static int32_t query_bound=4096;
static int32_t floor_index=-1;
int32_t player_floor_index(void) { return floor_index; }
void player_bind_query(const player_world_t *w,const uint16_t *floors,uint32_t floor_count,
                       const uint16_t *walls,uint32_t wall_count,int32_t bound,
                       const int16_t (*normals)[3]) {
    query_world=w;query_floors=floors;query_floor_count=floor_count;
    query_walls=walls;query_wall_count=wall_count;query_bound=bound;
    query_normals=normals;
}

// RV32I has no multiply/divide instruction. Explicit bounded integer routines
// keep the controller portable without compiler runtime libraries.
int32_t fixed_mul(int32_t a, int32_t b) {
    uint32_t x = a < 0 ? 0u-(uint32_t)a : (uint32_t)a;
    uint32_t y = b < 0 ? 0u-(uint32_t)b : (uint32_t)b;
    uint32_t result = 0;
    while (y) { if (y & 1u) result += x; x <<= 1; y >>= 1; }
    return (a < 0) != (b < 0) ? (int32_t)(0u-result) : (int32_t)result;
}
static uint32_t divide(uint32_t a, uint32_t b) {
    uint32_t q=0, bit=1;
    if (!b) return 0;
    while (b <= (a >> 1) && !(b & 0x80000000u)) { b <<= 1; bit <<= 1; }
    while (bit) { if (a >= b) { a -= b; q |= bit; } b >>= 1; bit >>= 1; }
    return q;
}
// floor(256*a/b), for 0<=a<b. Shifting a large source-space dot
// product by eight overflows; emit fractional bits from the remainder instead.
static uint32_t fraction8(uint32_t a,uint32_t b) {
    uint32_t q=0;
    for(uint32_t i=0;i<8;++i) {
        q<<=1;
        if(a>=b-a) { a-=b-a;q|=1; } else a+=a;
    }
    return q;
}
static int32_t cross(int32_t ax, int32_t az, int32_t bx, int32_t bz) {
    return fixed_mul(ax,bz)-fixed_mul(az,bx);
}
static int inside(int32_t e0, int32_t e1, int32_t e2) {
    return (e0 >= 0 && e1 >= 0 && e2 >= 0) || (e0 <= 0 && e1 <= 0 && e2 <= 0);
}
static int floor_contains(const collision_floor_t *f,int32_t x,int32_t z) {
    return x>=f->min_x && x<=f->max_x && z>=f->min_z && z<=f->max_z &&
        inside(cross(f->b.x-f->a.x,f->b.z-f->a.z,x-f->a.x,z-f->a.z),
               cross(f->c.x-f->b.x,f->c.z-f->b.z,x-f->b.x,z-f->b.z),
               cross(f->a.x-f->c.x,f->a.z-f->c.z,x-f->c.x,z-f->c.z));
}
static int32_t floor_height(const player_world_t *w,uint32_t i,int32_t x,int32_t z) {
    const collision_floor_t *f=w->floors+i;
    if (w==query_world && query_normals) {
        const int16_t *n=query_normals[i];
        int32_t numerator=fixed_mul(n[0],x-f->a.x)+fixed_mul(n[2],z-f->a.z);
        uint32_t height=divide(numerator<0?0u-(uint32_t)numerator:(uint32_t)numerator,(uint32_t)n[1]);
        return f->a.y-(numerator<0?-(int32_t)height:(int32_t)height);
    }
    return f->a.y+((fixed_mul(f->slope_x,x-f->a.x)+fixed_mul(f->slope_z,z-f->a.z)) >> 12);
}
int32_t player_floor(const player_world_t *w, int32_t x, int32_t z, int32_t ceiling) {
    int32_t best=NO_FLOOR;
    floor_index=-1;
    uint32_t count=w==query_world && query_floors?query_floor_count:w->floor_count;
    for (uint32_t q=0; q<count; ++q) {
        uint32_t i=w==query_world && query_floors?query_floors[q]:q;
        const collision_floor_t *f=w->floors+i;
        if (!floor_contains(f,x,z)) continue;
        int32_t y=floor_height(w,i,x,z);
        if (y<=ceiling && y>best) { best=y;floor_index=(int32_t)i; }
    }
    return best;
}
static int32_t square_distance(collision_point_t a, collision_point_t b) {
    int32_t x=a.x-b.x, y=a.y-b.y, z=a.z-b.z;
    return fixed_mul(x,x)+fixed_mul(y,y)+fixed_mul(z,z);
}
static int edge_hit(collision_point_t p, collision_point_t a, collision_point_t b, int32_t r2) {
    int32_t x=b.x-a.x, y=b.y-a.y, z=b.z-a.z;
    int32_t length=fixed_mul(x,x)+fixed_mul(y,y)+fixed_mul(z,z);
    int32_t dot=fixed_mul(p.x-a.x,x)+fixed_mul(p.y-a.y,y)+fixed_mul(p.z-a.z,z);
    if (dot<=0) return square_distance(p,a)<r2;
    if (dot>=length) return square_distance(p,b)<r2;
    uint32_t t=fraction8((uint32_t)dot,(uint32_t)length);
    collision_point_t q={(int16_t)(a.x+(fixed_mul(x,(int32_t)t)>>8)),
                         (int16_t)(a.y+(fixed_mul(y,(int32_t)t)>>8)),
                         (int16_t)(a.z+(fixed_mul(z,(int32_t)t)>>8))};
    return square_distance(p,q)<r2;
}
static int32_t projected_cross(collision_point_t a, collision_point_t b, collision_point_t p, uint32_t axis) {
    if (axis==0) return cross(b.y-a.y,b.z-a.z,p.y-a.y,p.z-a.z);
    if (axis==1) return cross(b.x-a.x,b.z-a.z,p.x-a.x,p.z-a.z);
    return cross(b.x-a.x,b.y-a.y,p.x-a.x,p.y-a.y);
}
static int sphere_hit(const collision_wall_t *t, collision_point_t p, int32_t radius, int32_t r2) {
    int32_t distance=(fixed_mul(t->nx,p.x-t->a.x)+fixed_mul(t->ny,p.y-t->a.y)+fixed_mul(t->nz,p.z-t->a.z))>>12;
    if (distance<=-radius || distance>=radius) return 0;
    collision_point_t q={(int16_t)(p.x-(fixed_mul(t->nx,distance)>>12)),
                         (int16_t)(p.y-(fixed_mul(t->ny,distance)>>12)),
                         (int16_t)(p.z-(fixed_mul(t->nz,distance)>>12))};
    if (inside(projected_cross(t->a,t->b,q,t->axis),projected_cross(t->b,t->c,q,t->axis),
               projected_cross(t->c,t->a,q,t->axis))) return 1;
    return edge_hit(p,t->a,t->b,r2) || edge_hit(p,t->b,t->c,r2) || edge_hit(p,t->c,t->a,r2);
}
static int blocked(const player_world_t *w, int32_t x, int32_t y, int32_t z) {
    int32_t r=w->radius-1, r2=fixed_mul(r,r);
    uint32_t count=w==query_world && query_walls?query_wall_count:w->wall_count;
    for (uint32_t q=0; q<count; ++q) {
        uint32_t i=w==query_world && query_walls?query_walls[q]:q;
        const collision_wall_t *t=w->walls+i;
        if (x+r<t->min_x || x-r>t->max_x || z+r<t->min_z || z-r>t->max_z ||
            y+w->height<t->min_y || y>t->max_y) continue;
        // Overlapping spheres approximate a vertical capsule, including edges.
        for (int32_t h=r; ; h+=r) {
            if (h>w->height-r) h=w->height-r;
            collision_point_t p={(int16_t)x,(int16_t)(y+h),(int16_t)z};
            if (sphere_hit(t,p,r,r2)) return 1;
            if (h==w->height-r) break;
        }
    }
    return 0;
}
void player_reset(player_t *p, const player_world_t *w) {
    p->x=w->spawn_x; p->y=w->spawn_y; p->z=w->spawn_z; p->velocity_y=0;
    p->grounded=1; p->facing=16; p->previous_keys=0;
}
static void move_axis(player_t *p, const player_world_t *w, int32_t dx, int32_t dz) {
    if (!dx && !dz) return;
    int32_t x=p->x+dx, z=p->z+dz, y=p->y;
    // A downward floor query deliberately excludes surfaces above its ceiling.
    // That exclusion must not permit a horizontal step through a rising plane.
    // Use the same conservative local candidates; overhead floors remain clear
    // when their plane is already above the starting feet/step allowance.
    int32_t ceiling=p->y+(p->grounded?w->step_height:0);
    uint32_t count=w==query_world && query_floors?query_floor_count:w->floor_count;
    for (uint32_t q=0;q<count;++q) {
        uint32_t i=w==query_world && query_floors?query_floors[q]:q;
        if (floor_contains(w->floors+i,x,z) && floor_height(w,i,x,z)>ceiling &&
            floor_height(w,i,p->x,p->z)<=ceiling) return;
    }
    int32_t floor=player_floor(w,x,z,p->y+w->step_height);
    if (p->grounded && floor!=NO_FLOOR && floor>=p->y-w->step_height) y=floor;
    if (!blocked(w,x,y,z)) { p->x=x; p->z=z; p->y=y; }
}
void player_step(player_t *p, const player_world_t *w, uint32_t keys) {
    if ((keys&PLAYER_RESET)==PLAYER_RESET) {
        if ((p->previous_keys&PLAYER_RESET)!=PLAYER_RESET) { player_reset(p,w); ++p->respawns; }
        p->previous_keys=keys; return;
    }
    int32_t dx=0,dz=0;
    if ((keys&3u)==PLAYER_LEFT) dx=-w->speed;
    if ((keys&3u)==PLAYER_RIGHT) dx=w->speed;
    if ((keys&12u)==PLAYER_FORWARD) dz=w->speed;
    if ((keys&12u)==PLAYER_BACK) dz=-w->speed;
    if (dx && dz) { int32_t speed=fixed_mul(w->speed,181)>>8; dx=dx>0?speed:-speed; dz=dz>0?speed:-speed; }
    if (dx || dz) {
        p->facing=dz>0 ? (dx>0?4u:(dx<0?28u:0u)) :
                  dz<0 ? (dx>0?12u:(dx<0?20u:16u)) : (dx>0?8u:24u);
    }
    // Generated profile limits speed to radius/2 to avoid crossing thin walls.
    move_axis(p,w,dx,0); move_axis(p,w,0,dz);
    int32_t floor=player_floor(w,p->x,p->z,p->y+w->step_height);
    if (p->grounded && (floor==NO_FLOOR || p->y-floor>w->step_height)) p->grounded=0;
    if ((keys&PLAYER_JUMP) && !(p->previous_keys&PLAYER_JUMP) && p->grounded) {
        p->velocity_y=w->jump_speed; p->grounded=0;
    }
    if (!p->grounded) {
        int32_t next=p->y+p->velocity_y;
        floor=player_floor(w,p->x,p->z,p->y+1);
        if (p->velocity_y<=0 && floor!=NO_FLOOR && next<=floor) {
            p->y=floor; p->velocity_y=0; p->grounded=1;
        } else if (p->velocity_y>0 && blocked(w,p->x,next,p->z)) {
            p->velocity_y=0;
        } else { p->y=next; p->velocity_y-=w->gravity; }
    }
    int32_t bound=w==query_world?query_bound:4096;
    if (p->y<w->kill_y || p->x<-bound || p->x>bound || p->z<-bound || p->z>bound) {
        player_reset(p,w); ++p->respawns;
    }
    p->previous_keys=keys;
}
