`include "mario-sdram-test_symbols.svh"
`include "soc_mario_top_tb.sv"
module sdram_mario_top_tb;
    soc_mario_top_tb #(
        .HEX_FILE("build/mario-sdram-test.hex"),.CAPTURE_STEM("build/mario-sdram"),
        .TEST_NAME("sdram_mario_top_tb"),.ENABLE_SDRAM(1),
        .PLAYER_ADDR(`MARIO_SDRAM_TEST_PLAYER_ADDR),.CLIP_ADDR(`MARIO_SDRAM_TEST_CLIP_ADDR),
        .ANIMATION_FRAME_ADDR(`MARIO_SDRAM_TEST_ANIMATION_FRAME_ADDR),
        .ANIMATION_CYCLES_ADDR(`MARIO_SDRAM_TEST_ANIMATION_CYCLES_ADDR),
        .UPLOAD_CYCLES_ADDR(`MARIO_SDRAM_TEST_UPLOAD_CYCLES_ADDR),.CPU_CYCLES_ADDR(`MARIO_SDRAM_TEST_CPU_CYCLES_ADDR)
    ) test();
endmodule
