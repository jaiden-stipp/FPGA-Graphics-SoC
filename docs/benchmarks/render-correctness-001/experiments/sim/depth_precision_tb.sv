`timescale 1ns/1ps
`include "renderer_types.svh"
module depth_precision_tb;
 logic clk=0,reset=1,clear=0,we=0,re=0;always #10 clk=~clk;
 logic [`GFX_DEPTH_BITS-1:0] value;
 wire [`GFX_DEPTH_BITS-1:0] q0,q1;wire v0,v1,busy;
 zbuffer_banked #(.FRAME_WIDTH(8),.FRAME_HEIGHT(4)) dut(.reset(reset),.raster_clk(clk),
   .clear_request(clear),.clear_busy(busy),.read_enable(re),.read_x(10'd2),.read_y(9'd1),.read_depth(q0),.read_valid(v0),
   .read_enable1(re),.read_x1(10'd3),.read_y1(9'd1),.read_depth1(q1),.read_valid1(v1),
   .write_enable(we),.write_x(10'd2),.write_y(9'd1),.write_depth(value),
   .write_enable1(we),.write_x1(10'd3),.write_y1(9'd1),.write_depth1(value));
 task sample(input integer n);
  @(negedge clk);we=1;re=1;value=n;
  @(negedge clk);if(!v0 || !v1 || q0!==value || q1!==value)$fatal(1,"same-edge depth forwarding %0d",n);
  we=0;
  @(negedge clk);if(q0!==value || q1!==value)$fatal(1,"stored depth %0d",n);
  re=0;
 endtask
 initial begin
  repeat(4)@(negedge clk);reset=0;
  sample(1);sample(127);sample(255);
`ifdef SOC_DEPTH12
  sample(256);sample(511);sample(512);sample(1024);sample(2048);sample(4095);
`endif
  @(negedge clk);clear=1;@(negedge clk);clear=0;
  while(busy)@(negedge clk);
  re=1;@(negedge clk);if(q0!==0 || q1!==0)$fatal(1,"all depth bitplanes clear");
  $display("PASS depth_precision_tb bits=%0d",`GFX_DEPTH_BITS);$finish;
 end
 initial begin #100000;$fatal(1,"timeout");end
endmodule
