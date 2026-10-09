`include "mario-castle-sdram-test_symbols.svh"
module castle_world_top_tb;
    quake_sdram_top_tb #(
        .HEX_FILE("build/mario-castle-sdram-test.hex"),
        .ASSET_FILE("build/mario-castle-sdram.assets.hex"),
        .CAPTURE_PREFIX("castle-world"),.TEST_NAME("castle_world_top_tb"),
        .PLAYER_ADDR(`MARIO_CASTLE_SDRAM_TEST_PLAYER_ADDR),
        .CPU_CYCLES_ADDR(`MARIO_CASTLE_SDRAM_TEST_CPU_CYCLES_ADDR),
        .FRAME_CYCLES_ADDR(`MARIO_CASTLE_SDRAM_TEST_FRAME_CYCLES_ADDR),
        .EXPECTED_TRIANGLES(0),.MIN_WORLD_PIXELS(5000),.STANDING_ONLY(1),.ENFORCE_BUDGET(0)
    ) scene();
endmodule
