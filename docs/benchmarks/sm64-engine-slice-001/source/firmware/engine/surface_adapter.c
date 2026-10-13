// Original loader functions and grids; only allocation/IR ingestion are adapted.
#include <stdint.h>
#include "src/engine/surface_load.c"
#include "terrain.inc"
static struct Surface engine_surface_pool[ENGINE_SURFACES];
static struct SurfaceNode engine_node_pool[ENGINE_NODES];
s32 gSurfaceNodesAllocated,gSurfacesAllocated;
s32 gNumStaticSurfaceNodes,gNumStaticSurfaces;
s16 gCheckingSurfaceCollisionsForCamera,gFindFloorIncludeSurfaceIntangible;
s16 *gEnvironmentRegions;
s32 gEnvironmentLevels[20];
uint32_t engine_surface_fault;
void engine_load_surfaces(void){
    sSurfacePool=engine_surface_pool;sSurfaceNodePool=engine_node_pool;sSurfacePoolSize=ENGINE_SURFACES;
    gSurfaceNodesAllocated=gSurfacesAllocated=0;engine_surface_fault=0;
    gEnvironmentRegions=(s16 *)engine_environment;
    clear_static_surfaces();clear_spatial_partition(&gDynamicSurfacePartition[0][0]);
    for(unsigned i=0;i<ENGINE_SURFACES;++i){
        // Original loader only reads the immutable coordinates/indices.
        s16 indices[3]={engine_triangles[i][0],engine_triangles[i][1],engine_triangles[i][2]};s16 *cursor=indices;
        struct Surface *surface=read_surface_data((s16 *)engine_vertices,&cursor);
        if(!surface){engine_surface_fault=1;continue;}
        surface->type=engine_triangles[i][3];surface->force=engine_triangles[i][4];
        surface->flags=surf_has_no_cam_collision(surface->type)?SURFACE_FLAG_NO_CAM_COLLISION:0;
        add_surface(surface,FALSE);
    }
    gNumStaticSurfaces=gSurfacesAllocated;gNumStaticSurfaceNodes=gSurfaceNodesAllocated;
    if(gSurfaceNodesAllocated>ENGINE_NODES || gSurfacesAllocated>ENGINE_SURFACES)engine_surface_fault=2;
}
uint32_t engine_surface_bytes(void){return sizeof(engine_surface_pool)+sizeof(engine_node_pool)+sizeof(gStaticSurfacePartition)+sizeof(gDynamicSurfacePartition);}
