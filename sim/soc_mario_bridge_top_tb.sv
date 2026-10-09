`include "soc_mario_top_tb.sv"
`include "mario-bridge-test_symbols.svh"
module soc_mario_bridge_top_tb;
    soc_mario_top_tb #(.HEX_FILE("build/mario-bridge-test.hex"),
                       .CAPTURE_STEM("build/mario-bridge"),
                       .TEST_NAME("soc_mario_bridge_top_tb"),
                       .PLAYER_ADDR(`MARIO_BRIDGE_TEST_PLAYER_ADDR),.CLIP_ADDR(`MARIO_BRIDGE_TEST_CLIP_ADDR),
                       .ANIMATION_FRAME_ADDR(`MARIO_BRIDGE_TEST_ANIMATION_FRAME_ADDR),
                       .ANIMATION_CYCLES_ADDR(`MARIO_BRIDGE_TEST_ANIMATION_CYCLES_ADDR),
                       .UPLOAD_CYCLES_ADDR(`MARIO_BRIDGE_TEST_UPLOAD_CYCLES_ADDR),
                       .CPU_CYCLES_ADDR(`MARIO_BRIDGE_TEST_CPU_CYCLES_ADDR)) fixture();
endmodule
