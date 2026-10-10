`timescale 1ns/1ps
`include "renderer_types.svh"
module projection_precision_tb #(parameter REQUIRE_ACCURACY=1);
 logic clk=0,reset=1,in_valid=0,in_ready,out_valid,out_ready=0,busy;
 always #10 clk=~clk;
 projection_config_t projection;
 triangle_3d_t in_data;
 triangle_data_t out_data,held;
 integer samples=0,max_error=0,ex,ey,dx,dy,delta;
 integer depths[10]='{8190,8191,8192,8193,8194,10922,10923,16384,16385,30000};
 transform_3d_pipeline #(.BACKFACE_CULL(0)) dut(
  .clk(clk),.reset(reset),.projection(projection),.in_data(in_data),.in_valid(in_valid),.in_ready(in_ready),
  .out_data(out_data),.out_valid(out_valid),.out_ready(out_ready),.busy(busy),.triangle_clipped(),.triangle_culled());
 function automatic integer floor_div(input integer n,input integer d);
  return n>=0?n/d:-((-n+d-1)/d);
 endfunction
 task automatic sample(input integer x,input integer y,input integer z);
  while(!in_ready)@(negedge clk);
  in_data='0;
  delta=z<1000?16:100;
  in_data.x0=x;in_data.y0=y;in_data.z0=z;
  in_data.x1=x+delta;in_data.y1=y;in_data.z1=z;
  in_data.x2=x;in_data.y2=y+delta;in_data.z2=z;in_data.color=8'h42;
  in_valid=1;@(negedge clk);in_valid=0;
  while(!out_valid)@(negedge clk);
  ex=160+floor_div(x*256,z);ey=120-floor_div(y*256,z);
  dx=integer'(out_data.x0)-ex;if(dx<0)dx=-dx;
  dy=integer'(out_data.y0)-ey;if(dy<0)dy=-dy;
  if(dx>max_error)max_error=dx;if(dy>max_error)max_error=dy;
  if(out_data.z0!=65536/z || out_data.color!=8'h42)$fatal(1,"depth/color mismatch");
  $display("PROJECT x=%0d y=%0d z=%0d screen=(%0d,%0d) reference=(%0d,%0d) error=(%0d,%0d)",x,y,z,out_data.x0,out_data.y0,ex,ey,dx,dy);
  if(REQUIRE_ACCURACY && (dx>1 || dy>1))$fatal(1,"projection exceeds one-pixel reference error");
  held=out_data;
  repeat(4)begin @(negedge clk);if(!out_valid || out_data!==held)$fatal(1,"output changed under backpressure");end
  out_ready=1;@(negedge clk);out_ready=0;samples++;
  while(busy)@(negedge clk);
 endtask
 initial begin
  in_data='0;projection='{16'sd256,16'sd256,16'sd160,16'sd120,16'sd257};
  repeat(4)@(negedge clk);reset=0;
  for(integer i=0;i<10;i++)begin sample(4000,1000,depths[i]);sample(-4000,-1000,depths[i]);end
  sample(80,40,257);sample(-80,-40,257);
  sample(80,40,300);sample(-80,-40,300);
  sample(80,40,512);sample(-80,-40,512);
  $display("MEASURE projection samples=%0d maximum_pixel_error=%0d",samples,max_error);
  $display("PASS projection_precision_tb");$finish;
 end
 initial begin #1000000;$fatal(1,"projection timeout");end
endmodule
