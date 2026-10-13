`timescale 1ns/1ps
`include "renderer_types.svh"
module sdram_exec_game_tb #(
 parameter HEX_FILE="build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated-exec-test.hex",
 parameter EXTERNAL_FILE="build/mario-castle-audit-fixed-sdram-direct-packed-mul-geometry-uncapped-interpolated-exec-test.external.txt",
 parameter TEST_NAME="sdram_exec_game_tb"
);
 logic clk=0,reset=1,load_hold=1;always #10 clk=~clk;
 wire [31:0] pc,scratch;wire initialized;wire [3:0] errors;
 wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
 wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
 soc_top #(.HEX_FILE(HEX_FILE),.ENABLE_SDRAM(1),.ENABLE_SDRAM_EXEC(1)) dut(
  .clk(clk),.reset(reset),.sdram_reset(reset),.load_hold(load_hold),.buttons(8'b0),.look_state(24'b0),
  .debug_pc(pc),.scratch(scratch),.error_flags(errors),.sdram_initialized(initialized),
  .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),
  .DRAM_WE_N(DRAM_WE_N),.DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
 sdram_device_model chip(.*);
 integer fd,scan,frames=0,cycles=0;logic [24:0] key;logic [31:0] value;
 initial begin
  fd=$fopen(EXTERNAL_FILE,"r");
  if(!fd)$fatal(1,"Missing executable game fixture");
  while(!$feof(fd))begin scan=$fscanf(fd,"%h %h\n",key,value);if(scan==2)chip.memory[key]=value;end
  $fclose(fd);repeat(5)@(negedge clk);reset=0;wait(initialized);@(negedge clk);load_hold=0;
  wait(scratch>=2 || scratch[31:16]==16'hdead);
  if(errors || scratch[31:16]==16'hdead || frames<2)$fatal(1,"SDRAM game failed PC=%h scratch=%h errors=%h frames=%0d",pc,scratch,errors,frames);
  $display("PASS %s (cached SDRAM game code/state, geometry worker, two raster lanes, two presented frames, %0d cycles)",TEST_NAME,cycles);$finish;
 end
 always @(posedge clk)if(!reset && !load_hold)begin
  cycles=cycles+1;
  if(dut.frame_done)begin
   if(dut.frame_statistics.triangles_submitted<100 || dut.frame_statistics.pixels_written<5000)$fatal(1,"Missing rendered world geometry");
   frames=frames+1;
  end
 end
 initial begin #400000000;$fatal(1,"SDRAM game timeout PC=%h scratch=%h",pc,scratch);end
endmodule
