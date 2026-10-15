`timescale 1ns/1ps
module sdram_instruction_cache_tb;
 logic clk=0,reset=1,invalidate=0,selected=0,advance=0;
 always #10 clk=~clk;
 logic [31:0] pc=32'h80000000;
 wire hit;wire [31:0] instruction,hits,misses,fills;
 wire request_valid,request_ready,response_valid,initialized;
 wire [24:0] request_address;wire [31:0] response_data;
 sdram_instruction_cache dut(.next_pc(pc),.read_hits(hits),.read_misses(misses),.fill_words(fills),.*);
 wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
 wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
 sdram_controller #(.POWERUP_CYCLES(20)) ctl(.clk(clk),.reset(reset),.request_valid(request_valid),.request_write(1'b0),.request_burst(1'b1),
  .request_address(request_address),.request_data(32'b0),.request_byte_enable(4'hf),.request_ready(request_ready),
  .response_valid(response_valid),.response_data(response_data),.initialized(initialized),
  .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),
  .DRAM_WE_N(DRAM_WE_N),.DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
 sdram_device_model chip(.*);
 task check(input [31:0] address,input [31:0] expected);
  @(negedge clk);pc=address;selected=1;#1;
  wait(hit);@(negedge clk);#1;
  if(instruction!==expected)$fatal(1,"Fetch %h got %h expected %h",pc,instruction,expected);
 endtask
 initial begin
  for(integer n=0;n<8;n++)begin chip.write_word(n,32'h10000000+n);chip.write_word(1024+n,32'h20000000+n);chip.write_word(32768+n,32'h30000000+n);end
  repeat(5)@(negedge clk);reset=0;wait(initialized);
  check(32'h8000001c,32'h10000007);
  for(integer n=0;n<8;n++)check(32'h80000000+n*4,32'h10000000+n);
  if(misses!=1 || fills!=8)$fatal(1,"Warm line refetched");
  check(32'h80001000,32'h20000000);
  check(32'h80000000,32'h10000000);
  check(32'h80020000,32'h30000000);
  if(misses!=4 || fills!=32)$fatal(1,"Conflicting/high-address tags");
  // Invalidate during a fill, including the final install beat. It must drain.
  for(integer target=3;target<=7;target=target+4)begin
   @(negedge clk);pc=32'h80000000;selected=1;
   wait(dut.waiting && dut.beat==target && response_valid);
   invalidate=1;selected=0;
   repeat(2)@(negedge clk);invalidate=0;
   wait(!dut.waiting && !dut.issuing);
   if(dut.valid!=0)$fatal(1,"Invalidated in-flight line installed");
   check(32'h80000000,32'h10000000);
   check(32'h80020000,32'h30000000);
  end
  // Reloaded code is visible after explicit invalidation; never mid-execution.
  @(negedge clk);selected=0;chip.write_word(32768,32'habcdef01);invalidate=1;
  @(negedge clk);invalidate=0;
  check(32'h80020000,32'habcdef01);
  $display("PASS sdram_instruction_cache_tb (all beats, warm hits, conflicting tags, addresses beyond 64K, in-flight/final-beat invalidation, code reload)");$finish;
 end
 initial begin #2000000;$fatal(1,"Fetch-cache test timeout");end
endmodule
