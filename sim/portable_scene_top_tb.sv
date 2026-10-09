`include "portable-quake-sdram-test_symbols.svh"
module portable_scene_top_tb;
    quake_sdram_top_tb #(
        .HEX_FILE("build/portable-quake-sdram-test.hex"),
        .ASSET_FILE("build/portable-quake-sdram.assets.hex"),
        .CAPTURE_PREFIX("portable-quake"),.TEST_NAME("portable_scene_top_tb"),
        .PLAYER_ADDR(`PORTABLE_QUAKE_SDRAM_TEST_PLAYER_ADDR),
        .CPU_CYCLES_ADDR(`PORTABLE_QUAKE_SDRAM_TEST_CPU_CYCLES_ADDR)
    ) scene();
endmodule
