`timescale 1ns/1ps
module packed_mmio_case #(parameter integer DEPTH=8)(output logic done=0);
 logic clk=0,reset=1;always #5 clk=~clk;
 logic [31:0] addr=0,wdata=0,rdata,scratch;logic[2:0]funct3=2;
 logic read_en=0,write_en=0,write_performed,byte_valid,byte_ready=0;
 logic[7:0]byte_data;logic frame_pending;logic[3:0]error_flags;
 soc_mmio #(.FIFO_DEPTH(DEPTH)) dut(.clk(clk),.reset(reset),.addr(addr),.wdata(wdata),.funct3(funct3),
 .read_en(read_en),.write_en(write_en),.rdata(rdata),.write_performed(write_performed),
 .byte_data(byte_data),.byte_valid(byte_valid),.byte_ready(byte_ready),.decoder_error(1'b0),.command_error(1'b0),
 .frame_done(1'b0),.frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),.look_state(24'b0),
 .cache_statistics(192'b0),.cpu_statistics(160'b0),.frame_pending(frame_pending),.error_flags(error_flags),.scratch(scratch));
 byte model[0:511];integer head=0,tail=0,pending=0,accepted=0,rejected=0,consumed=0;
 integer seed=32'h2914+DEPTH;logic[31:0]rng;
 task step(input integer n,input logic[31:0]word,input logic pop_enable,input logic legacy,input logic bad);
  logic expected_accept,consume;integer amount;
  @(negedge clk);addr=legacy?32'h40000000:32'h400000ac+4*n;
  wdata=word;write_en=n!=0;byte_ready=pop_enable;funct3=bad?0:2;
  #1;amount=legacy?1:n;expected_accept=write_en && !bad && DEPTH-pending>=amount;
  if(write_performed!==expected_accept)$fatal(1,"atomic acceptance depth=%0d count=%0d n=%0d",DEPTH,pending,amount);
  if(byte_valid !== (pending!=0))$fatal(1,"valid count mismatch");
  consume=byte_valid && byte_ready;
  if(consume && byte_data!==model[head])$fatal(1,"byte order depth=%0d expected=%h got=%h",DEPTH,model[head],byte_data);
  @(posedge clk);
  if(consume)begin head=(head+1)%512;pending=pending-1;consumed=consumed+1;end
  if(expected_accept)begin
   for(integer j=0;j<amount;j=j+1)begin model[tail]=word[j*8+:8];tail=(tail+1)%512;pending=pending+1;end
   accepted=accepted+1;
  end else if(write_en && !bad)rejected=rejected+1;
  #1;
  if(dut.count!==pending)$fatal(1,"occupancy mismatch depth=%0d",DEPTH);
 endtask
 initial begin
  repeat(3)@(negedge clk);reset=0;
  // Fill fully, then reject a packed transaction despite a simultaneous pop.
  for(integer i=0;i<DEPTH;i=i+1)step(1,i,0,1,0);
  step(4,32'h44332211,1,0,0);
  if(!error_flags[0])$fatal(1,"capacity rejection must report overflow");
  while(pending)step(0,0,1,1,0);
  for(integer i=0;i<1800;i=i+1)begin
   rng=$random(seed);step((rng>>4)%5,rng,rng[0],rng[1],rng[2] && rng[3]);
  end
  while(pending)step(0,0,1,1,0);
  // Every supported tail, starting at many wrap/bank positions.
  for(integer k=0;k<8;k=k+1)for(integer n=1;n<=4;n=n+1)begin
   step(n,32'h98abcdef,0,0,0);while(pending)step(0,0,1,1,0);
  end
  step(1,32'hdeadbeef,0,1,0);
  @(negedge clk);reset=1;write_en=0;byte_ready=0;
  @(negedge clk);reset=0;head=0;tail=0;pending=0;
  step(1,32'h12345678,1,0,0);step(0,0,1,1,0);
  if(!accepted || !rejected || !consumed)$fatal(1,"insufficient exercised transactions");
  $display("packed case depth=%0d accepted=%0d rejected=%0d consumed=%0d",DEPTH,accepted,rejected,consumed);done=1;
 end
endmodule
module packed_mmio_tb;
 wire[5:0]done;
 packed_mmio_case #(.DEPTH(2)) a(done[0]);packed_mmio_case #(.DEPTH(3)) b(done[1]);
 packed_mmio_case #(.DEPTH(4)) c(done[2]);packed_mmio_case #(.DEPTH(5)) d(done[3]);
 packed_mmio_case #(.DEPTH(12)) e(done[4]);packed_mmio_case #(.DEPTH(256)) f(done[5]);
 initial begin wait(&done);$display("PASS packed_mmio_tb");$finish;end
 initial begin #100000;$fatal(1,"packed MMIO timeout");end
endmodule
