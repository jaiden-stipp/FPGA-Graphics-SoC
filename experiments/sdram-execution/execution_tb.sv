`timescale 1ns/1ps
// Modes: 0 uncached I + 4K D; 1 shared 4K; 2 blocking 4K I + 4K D;
// 3 falling-edge 4K I + 4K D; 4 all-local reference; 5 local code overlays;
// 6 shared 8K (same total data-array capacity as the split caches).
module execution_tb #(parameter MODE=3,CASE_ID=0);
 logic clk=0,reset=1;always #10 clk=~clk;
 wire initialized;wire cpu_reset=reset || !initialized;
 wire [31:0] pc,addr,wdata,instruction,rdata,local_insn,local_data;
 wire [2:0] funct3;wire read_en,write_en,local_bad,local_write;
 wire ext_i=pc[31:27]==5'b10000,ext_d=addr[31:27]==5'b10000 && (read_en || write_en);
 logic i_wait=0,i_done=0,d_wait=0,d_done=0;
 logic [31:0] i_data=0,i_pc=0,i_saved_pc=0,d_data=0;
 wire [1:0] reqvalid,reqwrite,reqburst,reqready,resp;
 wire [24:0] reqaddr[0:1];wire [31:0] reqdata[0:1];wire [3:0] reqbytes[0:1];
 wire [31:0] respdata,i_response_data,d_response_data;wire fast_hit;wire [31:0] fast_instruction;
 wire i_ready=MODE==3?fast_hit:(i_done && i_pc==pc);
 wire stall=(ext_i && !i_ready) || (ext_d && !d_done);
 assign instruction=ext_i?(MODE==3?fast_instruction:i_data):local_insn;
 assign rdata=ext_d?d_data:local_data;
 wire trace_valid,trace_write;wire [31:0] trace_pc,trace_value,trace_instruction;wire [4:0] trace_rd;
 RV32I_SoC cpu(.clk(clk),.rst(cpu_reset),.debug_pc(pc),.soc_stall(stall),
  .soc_instruction(instruction),.soc_rdata(rdata),.soc_misaligned(local_bad),
  .soc_write_performed(local_write || (ext_d && d_done && write_en && !stall)),
  .soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),.soc_read_en(read_en),.soc_write_en(write_en),
  .trace_valid(trace_valid),.trace_pc(trace_pc),.trace_instruction(trace_instruction),.trace_reg_write(trace_write),.trace_rd(trace_rd),.trace_rd_data(trace_value));
 soc_ram #(.N(16384),.HEX_FILE("")) ram(.clk(clk),.pc(pc),.d_addr(addr),.d_wdata(wdata),.d_funct3(funct3),
  .dw_en(write_en && addr<65536 && !stall && !cpu_reset),.dr_en(read_en && addr<65536),
  .Instruction(local_insn),.d_rdata(local_data),.misaligned(local_bad),.write_performed(local_write));
 assign reqvalid[1]=ext_d && !d_wait && !d_done && !cpu_reset;
 assign reqwrite[1]=write_en;assign reqburst[1]=0;assign reqaddr[1]=addr[26:2];
 assign reqdata[1]=wdata;assign reqbytes[1]=15;
 // Directed workload uses aligned 32-bit accesses only.
 always_ff @(posedge clk)begin
  if(cpu_reset)begin i_wait<=0;i_done<=0;d_wait<=0;d_done<=0;i_pc<=0;i_saved_pc<=0;i_data<=0;d_data<=0;end
  else begin
   if(MODE!=3)begin
    if(reqvalid[0] && reqready[0])begin i_wait<=1;i_saved_pc<=pc;end
    if(resp[0])begin i_data<=i_response_data;i_pc<=i_saved_pc;i_done<=1;i_wait<=0;end
   end
   if(reqvalid[1] && reqready[1])d_wait<=1;
   if(resp[1])begin d_data<=d_response_data;d_done<=1;d_wait<=0;end
   // A MEM result remains held until BOTH fetch and MEM permit advancement.
   if(!stall)d_done<=0;
  end
 end
 wire [31:0] ih,im,ifills,dh,dm,dfills;
 generate if(MODE==3)begin
  execution_fetch_cache ic(.clk(clk),.reset(cpu_reset),.invalidate(1'b0),.selected(ext_i),.advance(!stall),.pc(pc),
   .hit(fast_hit),.instruction(fast_instruction),.request_valid(reqvalid[0]),.request_address(reqaddr[0]),
   .request_ready(reqready[0]),.response_valid(resp[0]),.response_data(i_response_data),.hits(ih),.misses(im),.fills(ifills));
  assign reqwrite[0]=0;assign reqburst[0]=1;assign reqdata[0]=0;assign reqbytes[0]=15;
 end else begin
  assign reqvalid[0]=ext_i && !i_ready && !i_wait && !cpu_reset;
  assign reqwrite[0]=0;assign reqburst[0]=0;assign reqaddr[0]=pc[26:2];assign reqdata[0]=0;assign reqbytes[0]=15;
  assign fast_hit=0;assign fast_instruction=0;
 end endgenerate
 wire mvalid,mwrite,mburst,mready,mresponse;wire [24:0] maddress;wire [31:0] mdata,mrdata;wire [3:0] mbytes;
 generate if(MODE==1 || MODE==6)begin
  wire cv,cw,cb,cr,cp;wire [24:0] ca;wire [31:0] cd,rd;wire [3:0] ce;
  execution_mux #(.BEATS(1)) front(.clk(clk),.reset(cpu_reset),.valid(reqvalid),.wr(reqwrite),.burst(reqburst),
   .address(reqaddr),.data(reqdata),.bytes(reqbytes),.ready(reqready),.response(resp),.rdata(respdata),
   .mvalid(cv),.mwrite(cw),.mburst(cb),.maddress(ca),.mdata(cd),.mbytes(ce),.mready(cr),.mresponse(cp),.mrdata(rd));
  execution_data_cache #(.CACHE_BYTES(MODE==6?8192:4096)) cache(.clk(clk),.reset(reset),.bypass(1'b0),.invalidate(cpu_reset),
   .request_valid(cv),.request_write(cw),.request_address(ca),.request_data(cd),.request_byte_enable(ce),
   .request_ready(cr),.response_valid(cp),.response_data(rd),
   .memory_valid(mvalid),.memory_write(mwrite),.memory_burst(mburst),.memory_address(maddress),.memory_data(mdata),.memory_byte_enable(mbytes),
   .memory_ready(mready),.memory_response_valid(mresponse),.memory_response_data(mrdata),.read_hits(ih),.read_misses(im),.fill_words(ifills));
  assign dh=0;assign dm=0;assign dfills=0;
  assign i_response_data=respdata;assign d_response_data=respdata;
 end else begin
  wire [1:0] v,w,b,ready2,response2;wire [24:0] a[0:1];wire [31:0] d[0:1];wire [3:0] e[0:1];wire [31:0] rd;
  sdram_cache dc(.clk(clk),.reset(reset),.bypass(1'b0),.invalidate(cpu_reset),
   .request_valid(reqvalid[1]),.request_write(reqwrite[1]),.request_address(reqaddr[1]),.request_data(reqdata[1]),.request_byte_enable(reqbytes[1]),
   .request_ready(reqready[1]),.response_valid(resp[1]),.response_data(d_response_data),
   .memory_valid(v[1]),.memory_write(w[1]),.memory_burst(b[1]),.memory_address(a[1]),.memory_data(d[1]),.memory_byte_enable(e[1]),
   .memory_ready(ready2[1]),.memory_response_valid(response2[1]),.memory_response_data(rd),.read_hits(dh),.read_misses(dm),.fill_words(dfills));
  if(MODE==2)begin
   wire [31:0] ir;
   sdram_cache ic(.clk(clk),.reset(reset),.bypass(1'b0),.invalidate(cpu_reset),
    .request_valid(reqvalid[0]),.request_write(1'b0),.request_address(reqaddr[0]),.request_data(32'b0),.request_byte_enable(4'hf),
    .request_ready(reqready[0]),.response_valid(resp[0]),.response_data(ir),
    .memory_valid(v[0]),.memory_write(w[0]),.memory_burst(b[0]),.memory_address(a[0]),.memory_data(d[0]),.memory_byte_enable(e[0]),
    .memory_ready(ready2[0]),.memory_response_valid(response2[0]),.memory_response_data(rd),.read_hits(ih),.read_misses(im),.fill_words(ifills));
   // Separate client response data must not share a driven net.
   assign i_response_data=ir;
  end else begin
   assign v[0]=reqvalid[0];assign w[0]=reqwrite[0];assign b[0]=reqburst[0];assign a[0]=reqaddr[0];assign d[0]=reqdata[0];assign e[0]=reqbytes[0];
   assign reqready[0]=ready2[0];assign resp[0]=response2[0];assign i_response_data=rd;
   if(MODE!=3)begin assign ih=0;assign im=0;assign ifills=0;end
  end
  execution_mux arb(.clk(clk),.reset(reset),.valid(v),.wr(w),.burst(b),.address(a),.data(d),.bytes(e),
   .ready(ready2),.response(response2),.rdata(rd),.mvalid(mvalid),.mwrite(mwrite),.mburst(mburst),.maddress(maddress),.mdata(mdata),.mbytes(mbytes),
   .mready(mready),.mresponse(mresponse),.mrdata(mrdata));
 end endgenerate
 // I/D caches hold independent response words. Shared mode routes one word.
 wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
 wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
 sdram_controller #(.POWERUP_CYCLES(20)) ctl(.clk(clk),.reset(reset),.request_valid(mvalid),.request_write(mwrite),.request_burst(mburst),
  .request_address(maddress),.request_data(mdata),.request_byte_enable(mbytes),.request_ready(mready),.response_valid(mresponse),.response_data(mrdata),
  .initialized(initialized),.DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),
  .DRAM_WE_N(DRAM_WE_N),.DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
 sdram_device_model chip(.*);
 integer cycles=0,retired=0,ifreeze=0,dfreeze=0,bothfreeze=0,transactions=0;
 logic [31:0] expected,trace_hash=0;logic [159:0] held_pcs;
 string local_file,external_file;integer fd,scan,trace_file;logic [24:0] key;logic [31:0] value;
 initial begin
  local_file=$sformatf("build/sdram-execution/case%0d-mode%0d.local.hex",CASE_ID,MODE);
  external_file=$sformatf("build/sdram-execution/case%0d-mode%0d.external.txt",CASE_ID,MODE);
  trace_file=$fopen($sformatf("build/sdram-execution/case%0d-mode%0d.retirement.txt",CASE_ID,MODE),"w");
  if(!trace_file)$fatal(1,"Cannot open retirement trace");
  #1;$readmemh(local_file,ram.mem);
  fd=$fopen(external_file,"r");if(!fd)$fatal(1,"Missing external fixture");
  scan=$fscanf(fd,"%h\n",expected);
  while(!$feof(fd))begin scan=$fscanf(fd,"%h %h\n",key,value);if(scan==2)chip.memory[key]=value;end
  $fclose(fd);repeat(5)@(negedge clk);reset=0;
 end
 always @(posedge clk)if(!cpu_reset)begin
  cycles=cycles+1;
  if(ext_i && !i_ready)ifreeze=ifreeze+1;
  if(ext_d && !d_done)dfreeze=dfreeze+1;
  if(ext_i && !i_ready && ext_d && !d_done)bothfreeze=bothfreeze+1;
  if(mvalid && mready)transactions=transactions+1;
  if(trace_valid)begin
   retired=retired+1;
   $fdisplay(trace_file,"%08h %08h %0d %02h %08h",trace_pc,trace_instruction,trace_write,trace_rd,trace_write?trace_value:32'b0);
   trace_hash={trace_hash[26:0],trace_hash[31:27]} ^ trace_pc ^ trace_instruction ^ (trace_write?trace_value:0);
   if(trace_write && trace_rd==31)begin
    if(trace_value!==expected)$fatal(1,"Wrong result mode=%0d case=%0d got=%h expected=%h",MODE,CASE_ID,trace_value,expected);
    if(chip.memory['h10000]!==32'(CASE_ID==2?0:256))$fatal(1,"Repeated/missing stores word0=%h",chip.memory['h10000]);
    if(chip.memory['h10001]!==32'(CASE_ID==1?512:0))$fatal(1,"Repeated/missing stores word1=%h",chip.memory['h10001]);
    $display("RESULT mode=%0d case=%0d cycles=%0d retired=%0d trace_hash=%0d i_freeze=%0d d_freeze=%0d both_freeze=%0d transactions=%0d i_hits=%0d i_misses=%0d i_fill_words=%0d d_hits=%0d d_misses=%0d d_fill_words=%0d read_commands=%0d read_beats=%0d",MODE,CASE_ID,cycles,retired,trace_hash,ifreeze,dfreeze,bothfreeze,transactions,ih,im,ifills,dh,dm,dfills,chip.read_commands,chip.read_beats);
    $fclose(trace_file);$display("PASS execution_tb");$finish;
   end
  end
  if(stall)begin
   held_pcs={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB};
   if(trace_valid)$fatal(1,"Retirement during freeze");
   #1;if(held_pcs!=={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB})$fatal(1,"Pipeline advanced during freeze");
  end
 end
 initial begin #100000000;$fatal(1,"Execution timeout PC=%h",pc);end
endmodule
