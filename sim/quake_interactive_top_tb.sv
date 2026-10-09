`include "quake-interactive-sdram-test_symbols.svh"
module quake_interactive_top_tb;
    quake_sdram_top_tb #(
        .HEX_FILE("build/quake-interactive-sdram-test.hex"),
        .ASSET_FILE("build/quake-interactive-sdram.assets.hex"),
        .CAPTURE_PREFIX("quake-interactive"),.TEST_NAME("quake_interactive_top_tb"),
        .PLAYER_ADDR(`QUAKE_INTERACTIVE_SDRAM_TEST_PLAYER_ADDR),
        .CPU_CYCLES_ADDR(`QUAKE_INTERACTIVE_SDRAM_TEST_CPU_CYCLES_ADDR),
        .EXPECTED_TRIANGLES(1224),.INTERACTIVE(1),.DEMO_STATE_ADDR(`QUAKE_INTERACTIVE_SDRAM_TEST_DEMO_STATE_ADDR)
    ) scene();
endmodule
