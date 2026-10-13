`timescale 1ns/1ps
module sdram_exec_protection_tb;
 logic clk=0,reset=1,soft_reset=0,load_hold=1,load_valid=0,load_write=0;
 always #10 clk=~clk;
 logic [31:0] pc=0,addr=0,wdata=0,load_addr=0,load_wdata=0;
 logic read_en=0,write_en=0;wire [31:0] instruction,load_rdata;
 wire load_ready,initialized,stall;wire [3:0] errors;
 wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
 wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
 soc_memory #(.HEX_FILE(""),.ENABLE_SDRAM(1),.ENABLE_SDRAM_EXEC(1)) memory(
  .clk(clk),.reset(reset || soft_reset || load_hold || !initialized),.sdram_reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(3'b010),
  .read_en(read_en),.write_en(write_en),.instruction(instruction),.cpu_stall(stall),.error_flags(errors),.sdram_initialized(initialized),
  .load_hold(load_hold),.load_valid(load_valid),.load_write(load_write),.load_addr(load_addr),.load_wdata(load_wdata),.load_ready(load_ready),.load_rdata(load_rdata),
  .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),.frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),
  .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
  .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
 sdram_device_model chip(.*);
 task access(input bit wr,input [31:0] address,input [31:0] data,input [31:0] expected);
  @(negedge clk);#1;load_addr=address;load_wdata=data;load_write=wr;load_valid=1;
  wait(load_ready);@(posedge clk);
  if(!wr && load_rdata!==expected)$fatal(1,"Owned loader response mismatch: %h",load_rdata);
  #1;load_valid=0;repeat(3)@(negedge clk);
 endtask
 initial begin
  repeat(5)@(negedge clk);reset=0;wait(initialized);
  access(1,32'h80000000,32'h00000013,0);
  @(negedge clk);#1;pc=32'h80000000;load_hold=0;#1;
  wait(!stall);@(negedge clk);#1;if(instruction!==32'h13)$fatal(1,"Initial code fetch");
  addr=32'h80000000;wdata=32'hdeadbeef;write_en=1;
  repeat(3)@(negedge clk);#1;
  if(!stall || !errors[3] || chip.memory[0]!==32'h13)$fatal(1,"Executable store was not protected");
  write_en=0;load_hold=1;
  access(0,32'h80000000,0,32'h13);
  access(1,32'h80000000,32'h00100093,0);
  @(negedge clk);#1;load_hold=0;#1;
  wait(!stall);@(negedge clk);#1;
  if(instruction!==32'h00100093)$fatal(1,"Reloaded code remained stale");
  pc=32'h81000000;repeat(3)@(negedge clk);#1;
  if(!stall || !errors[3] || memory.instruction_request)$fatal(1,"Non-executable fetch not rejected");
  load_hold=1;pc=0;repeat(3)@(negedge clk);
  // Cancel an accepted CPU data read, without the loader's normal settle delay.
  load_hold=0;addr=32'h81000000;read_en=1;
  wait(memory.external_memory.executable_bridge.bridge.accepted);
  @(negedge clk);#1;load_hold=1;read_en=0;
  access(1,32'h81000004,32'hcafef00d,0);
  access(0,32'h81000004,0,32'hcafef00d);
  if(memory.instruction_fetch.cache.valid!=0)$fatal(1,"Loader did not invalidate I-cache");
  $display("PASS sdram_exec_protection_tb (immutable code, invalid fetch halt/error, coherent reload, loader takeover during accepted MEM read)");$finish;
 end
 initial begin #2000000;$fatal(1,"Protection/takeover timeout");end
endmodule
