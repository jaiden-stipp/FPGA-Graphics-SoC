`timescale 1ns/1ps
module sdram_arbiter_tb;
 logic clk=0,reset=1;always #5 clk=~clk;
 logic cv=1,cw=0,cb=1,dv=1,cr,cp,dr,dp,mv,mw,mb,mready=1,mresp=0;
 logic[24:0]ca=10,da=200,ma;logic[31:0]cd=32'h1234,cdout,ddout,md,mdata=0;logic[3:0]cbytes=15,mbytes;
 sdram_command_arbiter dut(.clk(clk),.reset(reset),.cpu_valid(cv),.cpu_write(cw),.cpu_burst(cb),.cpu_address(ca),.cpu_data(cd),.cpu_bytes(cbytes),.cpu_ready(cr),.cpu_response(cp),.cpu_rdata(cdout),.dma_valid(dv),.dma_address(da),.dma_ready(dr),.dma_response(dp),.dma_rdata(ddout),.memory_valid(mv),.memory_write(mw),.memory_burst(mb),.memory_address(ma),.memory_data(md),.memory_bytes(mbytes),.memory_ready(mready),.memory_response(mresp),.memory_rdata(mdata));
 integer grant=0,owner=0,left=0,cycles=0,responses=0;
 always @(negedge clk)begin
  if(!reset)begin
   cycles=cycles+1;mresp=0;
   if(left>0 && cycles%3!=0)begin mresp=1;mdata=owner==1?32'hcafecafe:32'hd00dd00d;end
   mready=left==0 && cycles%4!=0;
  end
 end
 always @(posedge clk)if(!reset)begin
  if(cp || dp)begin
   if(cp && dp || (cp && owner!=1) || (dp && owner!=2))$fatal(1,"misrouted response");
   if((cp && cdout!=32'hcafecafe)||(dp && ddout!=32'hd00dd00d))$fatal(1,"wrong owner data");
   left=left-1;responses=responses+1;
  end
  if(mv && mready)begin
   if(left!=0)$fatal(1,"overlapping transaction");
   grant=grant+1;owner=dr?2:1;
   if(grant<=10 && owner!=(grant%2?1:2))$fatal(1,"fairness failure");
   if(owner==2 && (mw || !mb || mbytes!=15 || ma!=da))$fatal(1,"DMA read contract");
   left=(!mw && mb)?8:1;
  end
 end
 initial begin
  repeat(4)@(negedge clk);reset=0;
  wait(grant==10);@(negedge clk);cv=0;dv=0;wait(left==0);@(negedge clk);
  if(responses!=80)$fatal(1,"burst response loss");
  cw=1;cb=0;cv=1;wait(grant==11);@(negedge clk);cv=0;wait(left==0);@(negedge clk);
  if(responses!=81)$fatal(1,"write response length");
  $display("PASS sdram_arbiter_tb (contested round robin, burst ownership, non-overlap, write response)");$finish;
 end
 initial begin #200000;$fatal(1,"arbiter timeout");end
endmodule
