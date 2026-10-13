`timescale 1ns/1ps
module sdram_execution_tb;
 logic clk=0,reset=1,hold_cpu=1,load_valid=0,load_write=0;
 always #10 clk=~clk;
 logic [31:0] load_addr=0,load_wdata=0;
 wire [31:0] pc,addr,wdata,instruction,rdata,scratch,load_rdata;
 wire [2:0] funct3;wire read_en,write_en,bad,performed,stall,initialized,load_ready;
 wire [7:0] byte_data;wire byte_valid;wire [3:0] errors;
 wire cpu_reset=reset || hold_cpu || !initialized;
 wire trace_valid;wire [31:0] trace_pc;
    wire [31:0] fetch_next_pc;
 RV32I_SoC cpu(.clk(clk),.rst(cpu_reset),.debug_pc(pc),.soc_stall(stall),
  .soc_instruction(instruction),.soc_rdata(rdata),.soc_misaligned(bad),.soc_write_performed(performed),
  .soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),.soc_read_en(read_en),.soc_write_en(write_en),
  .trace_valid(trace_valid),.trace_pc(trace_pc),.soc_fetch_next_pc(fetch_next_pc));
 wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
 wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
 soc_memory #(.HEX_FILE("build/sdram-exec-test.hex"),.ENABLE_SDRAM(1),.ENABLE_SDRAM_EXEC(1)) memory(
  .clk(clk),.reset(cpu_reset),.sdram_reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(funct3),
  .fetch_next_pc(fetch_next_pc),.fetch_lookahead_valid(1'b1),
  .read_en(read_en),.write_en(write_en),.instruction(instruction),.rdata(rdata),.misaligned(bad),.write_performed(performed),
  .cpu_stall(stall),.sdram_initialized(initialized),.scratch(scratch),.error_flags(errors),
  .load_hold(hold_cpu),.load_valid(load_valid),.load_write(load_write),.load_addr(load_addr),.load_wdata(load_wdata),.load_ready(load_ready),.load_rdata(load_rdata),
  .byte_data(byte_data),.byte_valid(byte_valid),.byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
  .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),
  .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
  .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
 sdram_device_model chip(.*);
 integer fd,scan,bytes=0,cycles=0,overlap=0,far_retired=0;
 logic [24:0] key;logic [31:0] value;logic [159:0] saved_pcs;
 task loader_access(input bit wr,input [31:0] address,input [31:0] data,input [31:0] expected);
  @(negedge clk);#1;load_addr=address;load_wdata=data;load_write=wr;load_valid=1;
  wait(load_ready);@(posedge clk);
  if(!wr && load_rdata!==expected)$fatal(1,"Loader read %h got %h expected %h",address,load_rdata,expected);
  #1;load_valid=0;
  repeat(3)@(negedge clk);
 endtask
 always @(negedge clk)if(!cpu_reset && byte_valid)begin
  if(byte_data!==8'(bytes))$fatal(1,"Duplicated/lost FIFO byte n=%0d got=%h",bytes,byte_data);
  bytes=bytes+1;
 end
 always @(posedge clk)if(!cpu_reset)begin
  cycles=cycles+1;
  if(trace_valid && trace_pc>=32'h80010000)far_retired=far_retired+1;
  if(memory.fetch_stall && memory.ext_stall)overlap=overlap+1;
  if(stall)begin
   saved_pcs={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB};
   if(trace_valid)$fatal(1,"Retired during freeze");
   #1;if(saved_pcs!=={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB})$fatal(1,"Pipeline advanced during freeze");
  end
 end
 initial begin
  fd=$fopen("build/sdram-exec-test.external.txt","r");if(!fd)$fatal(1,"Missing diagnostic fixture");
  while(!$feof(fd))begin scan=$fscanf(fd,"%h %h\n",key,value);if(scan==2)chip.memory[key]=value;end
  $fclose(fd);repeat(5)@(negedge clk);reset=0;wait(initialized);
  // Real loader writes replace code before CPU release, with explicit readback.
  loader_access(1,32'h80010004,32'h00000013,0);
  loader_access(0,32'h80010004,0,32'h00000013);
  @(negedge clk);hold_cpu=0;
  wait(scratch==32'h5eec600d || scratch[31:16]==16'hdead);
  if(scratch!=32'h5eec600d || errors || bytes!=128 || overlap==0 || far_retired<32)$fatal(1,"Execution diagnostic failed scratch=%h errors=%h bytes=%0d overlap=%0d far=%0d",scratch,errors,bytes,overlap,far_retired);
  $display("SDRAM_EXEC cycles=%0d overlap_freezes=%0d far_retired=%0d bytes=%0d",cycles,overlap,far_retired,bytes);
  // Enter loader hold during an active instruction fill, then reload/restart.
  @(negedge clk);hold_cpu=1;
  repeat(70)@(negedge clk);
  loader_access(1,32'h80010004,32'h00000013,0);
  loader_access(0,32'h80010004,0,32'h00000013);
  bytes=0;@(negedge clk);hold_cpu=0;
  wait(memory.instruction_fetch.cache.waiting);
  @(negedge clk);hold_cpu=1;
  repeat(70)@(negedge clk);
  if(memory.instruction_fetch.cache.valid!=0)$fatal(1,"In-flight reload installed stale instruction line");
  loader_access(0,32'h80010004,0,32'h00000013);
  bytes=0;@(negedge clk);hold_cpu=0;
  wait(scratch==32'h5eec600d || scratch[31:16]==16'hdead);
  if(scratch!=32'h5eec600d || errors || bytes!=128)$fatal(1,"Reload did not execute cleanly");
  $display("PASS sdram_execution_tb (local boot, >64K executed image, BSS/data initialization, subword memory, FIFO exactly once, overlapping stalls, loader reload/miss invalidation)");$finish;
 end
 initial begin #40000000;$fatal(1,"SDRAM executable timeout pc=%h scratch=%h",pc,scratch);end
endmodule
