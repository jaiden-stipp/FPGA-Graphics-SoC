`timescale 1ns/1ps
module gfx_dma_tb;
 logic clk=0,reset=1,cancel=0,start=0;always #10 clk=~clk;
 logic[31:0]source=0,length=0,submission_id=0,completed_id,bytes_sent,read_words,request_wait,fifo_wait;
 logic busy,mv,mr,rv=0,bv,accepted=0;logic[24:0]ma;logic[31:0]rd=0;logic[7:0]data,error_code;
 gfx_command_dma dut(.clk(clk),.reset(reset),.cancel(cancel),.start(start),.source(source),.length(length),.submission_id(submission_id),
 .busy(busy),.error_code(error_code),.completed_id(completed_id),.bytes_sent(bytes_sent),.read_words(read_words),.request_wait(request_wait),.fifo_wait(fifo_wait),
 .memory_valid(mv),.memory_address(ma),.memory_ready(mr),.memory_response_valid(rv),.memory_response_data(rd),.byte_valid(bv),.byte_data(data),.byte_accepted(accepted));
 logic pending=0;integer delay=0,beat=0;logic[24:0]base;
 integer cycle=0,received=0,expected=0;logic checking=0;logic[31:0]expected_source;
 assign mr=!pending && cycle%5!=0;
 function automatic[31:0]word_at(input logic[24:0]a);
  logic[31:0]v;begin for(integer k=0;k<4;k=k+1)v[k*8+:8]=(a*4+k)&255;word_at=v;end
 endfunction
 always @(posedge clk)begin
  cycle<=cycle+1;rv<=0;
  if(reset)begin pending<=0;delay<=0;beat<=0;end
  else begin
   if(mv && mr)begin if(ma[2:0]!=0)$fatal(1,"unaligned burst");pending<=1;base<=ma;delay<=3;beat<=0;end
   if(pending)begin
    if(delay!=0)delay<=delay-1;
    else if(cycle%3!=0)begin rv<=1;rd<=word_at(base+beat);if(beat==7)pending<=0;else beat<=beat+1;end
   end
  end
 end
 always @(negedge clk)begin
  accepted=bv && cycle%7!=0 && cycle%11!=0;
  if(accepted && checking)begin
   if(received>=expected || data!==((expected_source+received)&255))$fatal(1,"DMA byte order index=%0d data=%h",received,data);
   received=received+1;
  end
 end
 task run(input integer n,input integer id);
  @(negedge clk);source=32'h80002000+id*32;length=n;submission_id=id;received=0;expected=n;expected_source=source;checking=1;start=1;
  @(negedge clk);start=0;wait(!busy);#1;
  if(error_code || completed_id!=id || received!=n)$fatal(1,"DMA completion n=%0d received=%0d",n,received);
  checking=0;
 endtask
 task invalid(input logic[31:0]s,input logic[31:0]n);
  @(negedge clk);source=s;length=n;start=1;@(negedge clk);start=0;wait(!busy);#1;
  if(busy || error_code!=1)$fatal(1,"bad descriptor accepted");
 endtask
 initial begin
  repeat(4)@(negedge clk);reset=0;
  for(integer n=1;n<=65;n=n+1)run(n,n);
  run(127,100);run(255,101);run(1024,102);run(4096,103);run(65535,108);run(65536,109);
  invalid(32'h80000001,32);invalid(32'h80000000,0);invalid(32'h80000000,65537);invalid(32'h87ffefe0,33);invalid(32'hffffffe0,32);
  // Cancel an already accepted burst and require complete drain before reuse.
  @(negedge clk);source=32'h80001000;length=100;submission_id=104;start=1;
  @(negedge clk);start=0;wait(dut.state==dut.FILL);@(negedge clk);cancel=1;
  wait(!busy);if(completed_id==104 || pending)$fatal(1,"cancel failed to drain");
  repeat(3)@(negedge clk);cancel=0;run(33,105);
  // Cancel an active stream; no publication may continue during hold.
  @(negedge clk);source=32'h80001000;length=100;submission_id=106;start=1;
  @(negedge clk);start=0;wait(bv);@(negedge clk);cancel=1;
  @(negedge clk);if(bv || busy || completed_id==106)$fatal(1,"stream cancel failed");
  cancel=0;run(17,107);
  if(!fifo_wait || !request_wait)$fatal(1,"backpressure not exercised");
  $display("PASS gfx_dma_tb (tails, bursts, backpressure, descriptor bounds, accepted-burst/stream cancellation)");$finish;
 end
 initial begin #30000000;$fatal(1,"DMA timeout");end
endmodule
