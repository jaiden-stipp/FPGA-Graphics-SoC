// Measurement fixture: resident indexed geometry isolates GPU-side overlap.
// Synthetic repeated faces are not an original-game performance claim.
#include "soc.h"
#include "gfx.h"
volatile uint32_t setup_results[3][14];
volatile uint32_t setup_clock;
static void check(int error) {
    if(error){SOC_SCRATCH=0xdead3301u;for(;;){}}
}
int main(void) {
    setup_clock=SOC_CLOCK_HZ;
    check(gfx_identity_view());check(gfx_projection(256,257));
    for(uint32_t mesh=0;mesh<3u;++mesh){
        int16_t half=mesh==0?4:mesh==1?32:64;
        check(gfx_define_mesh((uint8_t)mesh,3,128));
        check(gfx_vertex((uint8_t)mesh,0,-half,-half,512));
        check(gfx_vertex((uint8_t)mesh,1,half,-half,512));
        check(gfx_vertex((uint8_t)mesh,2,-half,half,512));
        for(uint32_t i=0;i<128u;++i)
            check(gfx_index((uint8_t)mesh,(uint16_t)i,0,1,2,(uint8_t)(i+1u)));
    }
    for(uint32_t mesh=0;mesh<3u;++mesh){
        check(gfx_begin_frame(mesh+1u));
        check(gfx_draw_mesh((uint8_t)mesh,0,0,0));
        check(gfx_end_frame());check(gfx_wait_frame(mesh+1u));
        for(uint32_t i=0;i<13u;++i)setup_results[mesh][i]=GFX_STAT(i);
        setup_results[mesh][13]=GFX_FRAME_ID;
    }
    if(GFX_ERRORS){SOC_SCRATCH=0xdead3302u;for(;;){}}
    SOC_SCRATCH=0x3300600du;for(;;){}
}
