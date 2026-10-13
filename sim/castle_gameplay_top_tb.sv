`timescale 1ns/1ps
module castle_gameplay_top_tb;
 sdram_exec_game_tb #(
  .HEX_FILE("build/mario-castle-gameplay-sdram-direct-packed-mul-geometry-uncapped-interpolated-exec-test.hex"),
  .EXTERNAL_FILE("build/mario-castle-gameplay-sdram-direct-packed-mul-geometry-uncapped-interpolated-exec-test.external.txt"),
  .TEST_NAME("castle_gameplay_top_tb")
 ) game();
endmodule
