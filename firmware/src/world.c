#include "world.h"
#include "soc.h"
#include "gfx.h"
#include "gfx_protocol.h"
#include "game_services.h"
#include "cpu_profile.h"
#include "geometry_worker.h"

// Diagnostic comparison only: preserve source meshes and physics while
// bypassing resident GPU handles for terrain. Actors still use mesh draws.
#ifndef WORLD_FORCE_DIRECT
#define WORLD_FORCE_DIRECT 0
#endif
#ifndef WORLD_GPU_FRACTIONAL
#define WORLD_GPU_FRACTIONAL 0
#endif
#ifndef WORLD_GPU_CAPABLE
#define WORLD_GPU_CAPABLE ((SOC_CPU_FEATURES & SOC_FEATURE_GPU_REGS) && (SOC_GPU_FEATURES & SOC_GPU_FEATURE_FRACTION))
#endif

// Fixed hardware; software cache uploads occur before BEGIN_FRAME only.
static const world_area_t *selected;
static const world_chunk_t *cache[16];
static int16_t prepared_matrix[16][12],prepared_view[12];
static uint8_t prepared_safe[16],prepared_fraction[16][3];
static int32_t prepared_position[3];
static uint16_t visible_chunks[2048];
static uint32_t room=1;
volatile uint32_t world_visible_chunks,world_direct_triangles,world_uploaded_chunks;
volatile uint32_t world_gpu_chunks,world_fallback_chunks;
typedef geometry_point_t clip_point_t;
// One reusable CPU scratch buffer. A source vertex shared by several faces
// keeps exactly one transform/outcode per direct-drawn mesh and frame.
static clip_point_t direct_points[128];
static uint8_t direct_outcodes[128];
static void word(uint8_t *p,int32_t x) { p[0]=(uint8_t)((uint16_t)x>>8);p[1]=(uint8_t)x; }
void world_collision(const world_area_t *a,const player_t *p) {
    int32_t x=(p->x-a->grid_x)>>9,z=(p->z-a->grid_z)>>9;
    if(x<0 || z<0 || (uint32_t)x>=a->grid_width || (uint32_t)z>=a->grid_depth) {
        player_bind_query(a->physics,0,0,0,0,16000,a->floor_normals);return;
    }
    const world_cell_t *c=a->cells+fixed_mul(z,(int32_t)a->grid_width)+x;
    player_bind_query(a->physics,a->floor_indices+c->floor_start,c->floor_count,
                      a->wall_indices+c->wall_start,c->wall_count,16000,a->floor_normals);
}
void world_select(const world_area_t *a,player_t *p) {
    selected=a;room=1;
    world_visible_chunks=0;
    for(uint32_t h=0;h<16;++h)cache[h]=0;
    player_reset(p,a->physics);world_collision(a,p);
}
int world_floor_contact(const world_area_t *a,const player_t *p,world_contact_t *contact) {
    world_collision(a,p);
    contact->height=player_floor(a->physics,p->x,p->z,p->y+a->physics->step_height);
    int32_t i=player_floor_index();
    contact->surface=i>=0 && a->floor_surfaces?a->floor_surfaces+i:0;
    contact->normal=i>=0 && a->floor_normals?a->floor_normals[i]:0;
    return i>=0;
}
const world_exit_t *world_exit_find(const world_exit_t *exits,uint32_t count,uint32_t area,uint32_t event) {
    for(uint32_t i=0;i<count;++i)
        if(exits[i].source_area==area && exits[i].event==event)return exits+i;
    return 0;
}
int32_t world_transition_find(const world_transition_t *ts,uint32_t count,uint32_t area,
    const player_t *p,uint32_t use,uint32_t stars,uint32_t keys) {
    for(uint32_t i=0;i<count;++i) {
        const world_transition_t *t=ts+i;
        if(t->source_area!=area || (!t->automatic && !use))continue;
        int32_t dx=p->x-t->position[0],dy=p->y-t->position[1],dz=p->z-t->position[2];
        if(dx<-(int32_t)t->radius || dx>t->radius || dz<-(int32_t)t->radius || dz>t->radius || dy< -100 || dy>300)continue;
        if(fixed_mul(dx,dx)+fixed_mul(dz,dz)>fixed_mul(t->radius,t->radius))continue;
        if(stars<t->required_stars || (keys&t->required_keys)!=t->required_keys)return -2;
        return (int32_t)i;
    }
    return -1;
}
static clip_point_t transform(int32_t x,int32_t y,int32_t z,const player_t *p,const int16_t *v) {
    clip_point_t q;
    x=(x-p->x)*4;y=(y-p->y)*4;z=(z-p->z)*4;
    q.x=((fixed_mul(x,v[0])+fixed_mul(y,v[1])+fixed_mul(z,v[2]))>>8)+v[3];
    q.y=((fixed_mul(x,v[4])+fixed_mul(y,v[5])+fixed_mul(z,v[6]))>>8)+v[7];
    q.z=((fixed_mul(x,v[8])+fixed_mul(y,v[9])+fixed_mul(z,v[10]))>>8)+v[11];
    return q;
}
// Explicit software frustum: focal 256, near 257, far 30000 GPU units.
// The far plane is a declared precision policy, never a mesh-cache truncation.
static int32_t plane(clip_point_t p,uint32_t k) {
    if(k==0)return p.z-257;if(k==1)return 30000-p.z;
    if(k==2)return p.x*256+p.z*160;
    if(k==3)return -p.x*256+p.z*160;
    if(k==4)return p.y*256+p.z*120;
    return -p.y*256+p.z*120;
}
static int32_t absolute(int32_t n) { return n<0?-n:n; }
static int visible(const world_chunk_t *c,const player_t *p,const int16_t *v) {
    if(c->room_mask && !(c->room_mask&(1u<<(room-1))))return 0;
    clip_point_t center=transform(c->origin[0],c->origin[1],c->origin[2],p,v);
    int32_t extent[3],radius[3];
    for(uint32_t i=0;i<3;++i) {
        int32_t a=c->origin[i]-c->bounds[i<<1],b=c->bounds[(i<<1)+1]-c->origin[i];
        extent[i]=(a>b?a:b)*4;
    }
    for(uint32_t row=0;row<3;++row) {
        uint32_t b=row<<2;
        radius[row]=((fixed_mul(extent[0],absolute(v[b]))+fixed_mul(extent[1],absolute(v[b+1]))+fixed_mul(extent[2],absolute(v[b+2]))+255)>>8)+2;
    }
    if(center.z+radius[2]<257 || center.z-radius[2]>30000)return 0;
    int32_t horizontal=radius[0]*256+radius[2]*160;
    int32_t vertical=radius[1]*256+radius[2]*120;
    return plane(center,2)+horizontal>=0 && plane(center,3)+horizontal>=0 &&
           plane(center,4)+vertical>=0 && plane(center,5)+vertical>=0;
}
static int safe_matrix(const world_chunk_t *c,const player_t *p,const int16_t *v,int16_t *m) {
    if(WORLD_GPU_FRACTIONAL && !WORLD_GPU_CAPABLE)return 0;
    // Bounds are absolute source-world coordinates, validated by the converter.
    // Restrict arithmetic so neither the CPU proof nor GPU products overflow.
    if(p->x<-32768 || p->x>32767 || p->y<-32768 || p->y>32767 || p->z<-32768 || p->z>32767)return 0;
    if(!c->mesh.vertex_count || c->mesh.vertex_count>128 || c->mesh.triangle_count>256)return 0;
    for(uint32_t row=0;row<3;++row) {
        uint32_t b=row<<2;
        for(uint32_t j=0;j<3;++j)if(v[b+j]<-256 || v[b+j]>256)return 0;
        // Legacy GPU draws need integral origin translation. Fractional draws
        // carry its unsigned remainder into the local dot before flooring,
        // matching the CPU's combined floor, including negative coordinates.
        int32_t x=(c->origin[0]-p->x)*4,y=(c->origin[1]-p->y)*4,z=(c->origin[2]-p->z)*4;
        int32_t sum=fixed_mul(x,v[b])+fixed_mul(y,v[b+1])+fixed_mul(z,v[b+2]);
        if(!WORLD_GPU_FRACTIONAL && (sum&255))return 0;
    }
    clip_point_t q=transform(c->origin[0],c->origin[1],c->origin[2],p,v);
    if(q.x<-32764 || q.x>32764 || q.y<-32764 || q.y>32764 || q.z<-32764 || q.z>30000)return 0;
    for(uint32_t i=0;i<12;++i)m[i]=(i&3)==3?0:(int16_t)(v[i]*4);
    m[3]=(int16_t)q.x;m[7]=(int16_t)q.y;m[11]=(int16_t)q.z;
    int32_t lo[3]={32767,32767,32767},hi[3]={-32768,-32768,-32768};
    for(uint32_t j=0;j<3;++j)if(c->bounds[j*2]>c->bounds[j*2+1])return 0;
    // Eight corners bound every transformed vertex; no per-vertex admission
    // scan is needed on subsequent frames. A full camera-space box must fit.
    for(uint32_t i=0;i<8;++i) {
        q=transform(c->bounds[i&1],c->bounds[2+((i>>1)&1)],c->bounds[4+((i>>2)&1)],p,v);
        int32_t value[3]={q.x,q.y,q.z};
        for(uint32_t j=0;j<3;++j) {
            if(value[j]<lo[j])lo[j]=value[j];
            if(value[j]>hi[j])hi[j]=value[j];
        }
    }
    if(lo[0]<-32764 || hi[0]>32764 || lo[1]<-32764 || hi[1]>32764 || lo[2]<257 || hi[2]>30000)return 0;
    // Fully inside all CPU planes: the CPU would not change these triangles.
    // GPU projection/screen clipping then sees exactly the same coordinates.
    return lo[0]*256+lo[2]*160>=0 && -hi[0]*256+lo[2]*160>=0 &&
           lo[1]*256+lo[2]*120>=0 && -hi[1]*256+lo[2]*120>=0;
}
static int matrix(const world_chunk_t *c,const player_t *p,const int16_t *v,int16_t *m) {
    FINE_START(admission_start);
    int result=safe_matrix(c,p,v,m);
    FINE_END(PROFILE_ADMISSION,admission_start);
    if(result)FINE_EVENT(EVENT_GPU_ADMITTED);
    return result;
}
static int bounds_valid(const world_chunk_t *c) {
    // Validate the converter's box once before residency; retain original
    // vertices. A bad box never authorizes GPU saturation or different clipping.
    for(uint32_t i=0;i<c->mesh.vertex_count;++i) {
        const scene_vertex_t *s=c->mesh.vertices+i;
        int32_t q[3]={s->x+c->origin[0],s->y+c->origin[1],s->z+c->origin[2]};
        for(uint32_t j=0;j<3;++j)if(q[j]<c->bounds[2*j] || q[j]>c->bounds[2*j+1])return 0;
    }
    return 1;
}
static int upload(uint32_t h,const world_chunk_t *c) {
    FINE_START(upload_start);
    const scene_mesh_t *m=&c->mesh;
    if(gfx_define_mesh((uint8_t)h,m->vertex_count,m->triangle_count) ||
       game_mesh_frame((uint8_t)h,m->vertices,m->vertex_count))return -1;
    for(uint32_t start=0;start<m->triangle_count;) {
        uint32_t n=m->triangle_count-start;if(n>62)n=62;
        uint8_t data[252];data[0]=(uint8_t)h;word(data+1,(int32_t)start);data[3]=(uint8_t)n;
        for(uint32_t i=0;i<n;++i) {
            const scene_triangle_t *t=m->triangles+start+i;uint32_t b=4+(i<<2);
            data[b]=t->a;data[b+1]=t->b;data[b+2]=t->c;data[b+3]=t->color;
        }
        if(gfx_command(GFX_OP_UPLOAD_INDICES,data,(uint8_t)(4+(n<<2))))return -1;
        start+=n;
    }
    FINE_END(PROFILE_UPLOAD,upload_start);
    FINE_EVENT(EVENT_UPLOAD);
    return 0;
}
int world_prepare(const world_area_t *a,const player_t *p,const int16_t v[12],uint32_t reserved) {
    if(selected!=a || reserved>15 || a->chunk_count>2048)return -1;
    world_collision(a,p);(void)player_floor(a->physics,p->x,p->z,p->y+100);
    int32_t fi=player_floor_index();
    if(fi>=0 && a->floor_rooms && a->floor_rooms[fi]>0 && a->floor_rooms[fi]<=32)room=a->floor_rooms[fi];
    world_visible_chunks=0;world_uploaded_chunks=0;
    prepared_position[0]=p->x;prepared_position[1]=p->y;prepared_position[2]=p->z;
    for(uint32_t i=0;i<12;++i)prepared_view[i]=v[i];
    for(uint32_t h=0;h<16;++h)prepared_safe[h]=0;
    DETAIL_START(visibility_start);
    for(uint32_t h=reserved;h<16;++h) {
        if(cache[h] && !visible(cache[h],p,v))cache[h]=0;
    }
    for(uint32_t i=0;i<a->chunk_count;++i) {
        const world_chunk_t *c=a->chunks+i;
        if(c->render_flags&WORLD_RENDER_DEFERRED)continue;
        if(!visible(c,p,v))continue;
        visible_chunks[world_visible_chunks++]=(uint16_t)i;
        uint32_t found=16,free=16;int16_t m[12];
        for(uint32_t h=reserved;h<16;++h) {
            if(cache[h]==c)found=h;
            if(!cache[h] && free==16)free=h;
        }
        if(!WORLD_FORCE_DIRECT && (found<16 || free<16) && matrix(c,p,v,m)) {
            uint32_t h=found<16?found:free;
            if(found==16) {
                if(!bounds_valid(c))continue;
                if(upload(h,c))return -1;
                cache[h]=c;++world_uploaded_chunks;
            }
            for(uint32_t j=0;j<12;++j)prepared_matrix[h][j]=m[j];
            prepared_safe[h]=1;
            if(WORLD_GPU_FRACTIONAL)for(uint32_t row=0;row<3;++row) {
                uint32_t b=row<<2;
                int32_t sum=fixed_mul((c->origin[0]-p->x)*4,v[b])+fixed_mul((c->origin[1]-p->y)*4,v[b+1])+fixed_mul((c->origin[2]-p->z)*4,v[b+2]);
                prepared_fraction[h][row]=(uint8_t)sum;
            }
        }
    }
    DETAIL_END(PROFILE_VISIBILITY,visibility_start);
    return 0;
}
static uint32_t fraction(uint32_t n,uint32_t d) {
    FINE_START(fraction_start);
    uint32_t q=0;if(n>=d) { FINE_END(PROFILE_FRACTION,fraction_start); return 65536; }
    for(uint32_t i=0;i<16;++i) {
        q<<=1;
        if(n>=d-n) { n-=d-n;q|=1; }else n<<=1;
    }
    FINE_END(PROFILE_FRACTION,fraction_start);
    return q;
}
// Exact floor(delta*t/65536), without requiring MULH, 64-bit helpers or a
// potentially overflowing delta*t. fixed_mul supplies the low product bits.
static int32_t interpolate(int32_t a,int32_t b,int32_t t) {
    int32_t delta=b-a;
    if(t==65536)return b;
    return a+fixed_mul(delta>>16,t)+
        (int32_t)((uint32_t)fixed_mul((int32_t)((uint32_t)delta&65535u),t)>>16);
}
static clip_point_t intersection(clip_point_t a,clip_point_t b,int32_t da,int32_t db) {
    FINE_START(intersection_start);
    // Adjacent faces traverse their shared edge in opposite directions.
    // Quantize the fraction from a canonical endpoint so both emit one point.
    if(a.x>b.x || (a.x==b.x && (a.y>b.y || (a.y==b.y && a.z>b.z)))) {
        clip_point_t point=a;a=b;b=point;
        int32_t distance=da;da=db;db=distance;
    }
    uint32_t na=da<0?0u-(uint32_t)da:(uint32_t)da;
    uint32_t nb=db<0?0u-(uint32_t)db:(uint32_t)db;
    int32_t t=(int32_t)fraction(na,na+nb);clip_point_t q;
    q.x=interpolate(a.x,b.x,t);q.y=interpolate(a.y,b.y,t);q.z=interpolate(a.z,b.z,t);
    FINE_END(PROFILE_INTERSECTION,intersection_start);
    return q;
}
static int direct(const scene_triangle_t *t) {
    DETAIL_START(clip_start);
    clip_point_t polygon[12],out[12];uint32_t count=3;uint8_t indices[3]={t->a,t->b,t->c};
    for(uint32_t i=0;i<3;++i) {
        polygon[i]=direct_points[indices[i]];
    }
    uint32_t outside_all=63,outside_any=0;
    for(uint32_t i=0;i<3;++i) {
        uint32_t outside=direct_outcodes[indices[i]];
        outside_all&=outside;outside_any|=outside;
    }
    if(outside_all) { FINE_EVENT(EVENT_CLIP_REJECT); DETAIL_END(PROFILE_CLIPPING,clip_start); return 0; }
    if(!outside_any)FINE_EVENT(EVENT_CLIP_ACCEPT);
    for(uint32_t k=0;k<6 && count;++k) {
        if(!(outside_any&(1u<<k)))continue;
        uint32_t n=0;
        for(uint32_t i=0;i<count;++i) {
            clip_point_t a=polygon[i],b=polygon[i+1==count?0:i+1];int32_t da=plane(a,k),db=plane(b,k);
            if(da>=0)out[n++]=a;
            if((da<0)!=(db<0)) {
                out[n]=intersection(a,b,da,db);
                if(k==0)out[n].z=257;if(k==1)out[n].z=30000;
                ++n;
            }
        }
        count=n;for(uint32_t i=0;i<n;++i)polygon[i]=out[i];
    }
    DETAIL_END(PROFILE_CLIPPING,clip_start);
    for(uint32_t i=1;i+1<count;++i) {
        clip_point_t tri[3]={polygon[0],polygon[i],polygon[i+1]};uint8_t data[19];
        for(uint32_t j=0;j<3;++j) {
            if(tri[j].x<-32768 || tri[j].x>32767 || tri[j].y<-32768 || tri[j].y>32767 || tri[j].z<0 || tri[j].z>32767)return -1;
            word(data+6*j,tri[j].x);word(data+6*j+2,tri[j].y);word(data+6*j+4,tri[j].z);
        }
        data[18]=t->color;
        if(gfx_command(GFX_OP_DRAW_TRIANGLE,data,19))return -1;
        ++world_direct_triangles;
    }
    return 0;
}
int world_draw_instance(const scene_mesh_t *mesh,const int32_t position[3],int32_t co,int32_t si,
                        const player_t *p,const int16_t v[12]) {
    if(mesh->vertex_count>128 || mesh->triangle_count>256)return -1;
    for(uint32_t j=0;j<mesh->vertex_count;++j) {
        const scene_vertex_t *s=mesh->vertices+j;
        int32_t x=position[0]+((fixed_mul(s->x,co)+fixed_mul(s->z,si))>>8);
        int32_t z=position[2]+((fixed_mul(s->z,co)-fixed_mul(s->x,si))>>8);
        direct_points[j]=transform(x,position[1]+s->y,z,p,v);
        uint8_t code=0;
        for(uint32_t k=0;k<6;++k)if(plane(direct_points[j],k)<0)code|=(uint8_t)(1u<<k);
        direct_outcodes[j]=code;
    }
    for(uint32_t j=0;j<mesh->triangle_count;++j) {
        const scene_triangle_t *t=mesh->triangles+j;
        if(t->a>=mesh->vertex_count || t->b>=mesh->vertex_count || t->c>=mesh->vertex_count)return -1;
        if(direct(t))return -1;
    }
    return 0;
}
int world_draw(const world_area_t *a,const player_t *p,const int16_t v[12],uint32_t reserved) {
    if(selected!=a || reserved>15)return -1;
    world_direct_triangles=0;world_gpu_chunks=0;world_fallback_chunks=0;
    uint32_t same=p->x==prepared_position[0] && p->y==prepared_position[1] && p->z==prepared_position[2];
    for(uint32_t j=0;j<12;++j)if(v[j]!=prepared_view[j])same=0;
    for(uint32_t i=0;i<world_visible_chunks;++i) {
        const world_chunk_t *c=a->chunks+visible_chunks[i];
        if(c->render_flags&WORLD_RENDER_DEFERRED)continue;
        uint32_t handle=16;
        for(uint32_t h=reserved;h<16;++h)if(cache[h]==c)handle=h;
        if(!WORLD_FORCE_DIRECT && same && handle<16 && prepared_safe[handle]) {
            if(WORLD_GPU_FRACTIONAL) {
                uint8_t data[28];data[0]=(uint8_t)handle;
                for(uint32_t j=0;j<12;++j)word(data+1+2*j,prepared_matrix[handle][j]);
                for(uint32_t j=0;j<3;++j)data[25+j]=prepared_fraction[handle][j];
                if(gfx_command(GFX_OP_DRAW_MESH_Q8,data,28))return -1;
            }else if(gfx_draw_matrix((uint8_t)handle,prepared_matrix[handle]))return -1;
            ++world_gpu_chunks;FINE_EVENT(EVENT_GPU_DRAW);
        }
        else {
            ++world_fallback_chunks;FINE_EVENT(EVENT_DIRECT_DRAW);
            if(c->mesh.vertex_count>128)return -1;
            DETAIL_START(vertex_start);
#ifdef SOC_GEOMETRY_OFFLOAD
            int32_t position[3]={p->x,p->y,p->z};
            int accelerated=geometry_transform(c->mesh.vertices,c->mesh.vertex_count,c->origin,position,v,direct_points,direct_outcodes);
            if(accelerated<0)return -1;
            if(!accelerated)
#endif
            for(uint32_t j=0;j<c->mesh.vertex_count;++j) {
                const scene_vertex_t *s=c->mesh.vertices+j;
                direct_points[j]=transform(s->x+c->origin[0],s->y+c->origin[1],s->z+c->origin[2],p,v);
                uint8_t code=0;
                for(uint32_t k=0;k<6;++k)if(plane(direct_points[j],k)<0)code|=(uint8_t)(1u<<k);
                direct_outcodes[j]=code;
            }
            DETAIL_END(PROFILE_VERTICES,vertex_start);
            for(uint32_t j=0;j<c->mesh.triangle_count;++j)if(direct(c->mesh.triangles+j))return -1;
        }
    }
    return 0;
}
