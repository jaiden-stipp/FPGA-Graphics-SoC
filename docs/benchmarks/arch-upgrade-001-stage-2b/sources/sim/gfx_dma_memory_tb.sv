`timescale 1ns/1ps
module gfx_dma_memory_tb;
 localparam CACHE_ENABLED=1,BURST_ENABLED=1,CACHE_LINE_BYTES=32;
    localparam LINE_WORDS=CACHE_LINE_BYTES/4;
    logic cpu_reset=1;logic clk=0, reset=1; always #10 clk=~clk;
    logic [31:0] addr=0,wdata=0,rdata;
    logic [2:0] funct3=2;
    logic read_en=0,write_en=0,stall,bad,performed,initialized;
    logic load_hold=0,load_valid=0,load_ready;
    logic [31:0] load_addr=0,load_rdata;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    logic [31:0] refresh_count;
    wire[7:0]byte_data;wire byte_valid;logic byte_ready=0;wire[3:0]errors;
    soc_memory #(.HEX_FILE(""),.ENABLE_SDRAM(1),.ENABLE_CACHE(CACHE_ENABLED),.ENABLE_BURST(BURST_ENABLED),.CACHE_LINE_BYTES(CACHE_LINE_BYTES)) dut (
        .clk(clk),.reset(cpu_reset),.sdram_reset(reset),.pc(32'b0),.addr(addr),.wdata(wdata),
        .funct3(funct3),.read_en(read_en),.write_en(write_en),.rdata(rdata),
        .cpu_stall(stall),.misaligned(bad),.write_performed(performed),
        .sdram_initialized(initialized),.refresh_count(refresh_count),
        .load_hold(load_hold),.load_valid(load_valid),.load_write(1'b0),
        .load_addr(load_addr),.load_wdata(32'b0),.load_ready(load_ready),.load_rdata(load_rdata),
        .byte_ready(byte_ready),.byte_data(byte_data),.byte_valid(byte_valid),.error_flags(errors),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);

 integer received=0,expected=0,ticks=0;logic checking=0;
 always @(negedge clk)begin
  if(!cpu_reset && byte_valid && byte_ready && checking)begin
   if(byte_data!==((received*13+expected)&255))$fatal(1,"DMA integrated byte %0d got %h",received,byte_data);
   received=received+1;
  end
 end
 always @(posedge clk)begin ticks=ticks+1;#2;byte_ready=ticks%7<3;end
 task store(input[31:0]a,v);
  @(posedge clk);#1;addr=a;wdata=v;write_en=1;read_en=0;
  #1;
  if(a[31])begin do @(posedge clk);while(stall);end
  else begin if(!performed || bad)$fatal(1,"MMIO store %h rejected",a);@(posedge clk);end
  #1;if(a[31] && (!performed || bad))$fatal(1,"Store %h rejected",a);write_en=0;
 endtask
 task get(input[31:0]a,v);
  @(posedge clk);#1;addr=a;read_en=1;write_en=0;#1;
  if(a[31])begin do @(posedge clk);while(stall);end
  else @(posedge clk);
  if(rdata!==v)$fatal(1,"Read %h got %h expected %h",a,rdata,v);
  #1;read_en=0;
 endtask
 task submit(input[31:0]source,n,id);
  store(32'h400000c4,source);store(32'h400000c8,n);store(32'h400000cc,id);store(32'h400000d0,1);
 endtask
 initial begin
  repeat(5)@(posedge clk);#1;reset=0;cpu_reset=0;wait(initialized);
  get(32'h400000a8,7);get(32'h400000c0,32'h444d0101);
  // CPU write-through publication into a buffer crossing an SDRAM row end.
  for(integer k=0;k<264;k=k+4)begin
   logic[31:0]word;word=0;
   for(integer j=0;j<4;j=j+1)word[j*8+:8]=((k+j)*13+17)&255;
   store(32'h80000fe0+k,word);
  end
  expected=17;received=0;checking=1;submit(32'h80000fe0,259,1);
  // Cache misses and stores contend with DMA; no stale or cross-owned replies.
  store(32'h80004000,32'hdeadbeef);get(32'h80004000,32'hdeadbeef);
  wait(!dut.dma_busy);wait(received==259);checking=0;
  get(32'h400000d8,1);get(32'h400000e0,259);get(32'h400000e4,72);
  if(errors)$fatal(1,"Unexpected MMIO errors");
  // Illegal CPU enqueue while DMA owns the stream is rejected atomically.
  byte_ready=0;submit(32'h80000fe0,259,2);wait(dut.dma_busy);
  @(posedge clk);#1;addr=32'h40000000;wdata=0;write_en=1;#1;
  if(performed)$fatal(1,"CPU enqueue accepted while DMA busy");
  @(posedge clk);#1;write_en=0;
  if(!errors[0])$fatal(1,"Missing CPU ownership error");
  // Loader restart flushes FIFO, suppresses old bytes, drains burst ownership.
  wait(dut.command_transfer.dma.state==dut.command_transfer.dma.FILL);
  @(posedge clk);#1;load_hold=1;cpu_reset=1;load_valid=1;load_addr=32'h80004000;
  do @(posedge clk);while(!load_ready);
  if(load_rdata!==32'hdeadbeef)$fatal(1,"Loader response ownership");
  #1;load_valid=0;wait(!dut.dma_busy);
  repeat(3)@(posedge clk);#1;load_hold=0;cpu_reset=0;
  repeat(3)@(posedge clk);
  if(byte_valid || errors)$fatal(1,"Restart retained stale bytes/errors");
  expected=17;received=0;checking=1;submit(32'h80000fe0,33,3);
  wait(!dut.dma_busy);wait(received==33);checking=0;get(32'h400000d8,3);
  $display("PASS gfx_dma_memory_tb (actual SDRAM, cache contention, FIFO, restart)");$finish;
 end
 initial begin #3000000;$fatal(1,"DMA memory timeout received=%0d",received);end
endmodule
