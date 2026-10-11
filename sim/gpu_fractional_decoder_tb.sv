`timescale 1ns/1ps
`include "renderer_types.svh"
module gpu_fractional_decoder_tb;
 logic clk=0,reset=1,valid=0,ready,out_valid,out_ready=0,error;logic seen_error=0;
 always @(posedge clk)if(reset)seen_error<=0;else if(error)seen_error<=1;
 logic [7:0] data;graphics_command_t cmd,held;
 always #10 clk=~clk;
 graphics_command_stream_decoder dut(.clk(clk),.reset(reset),.byte_data(data),.byte_valid(valid),.byte_ready(ready),.command_data(cmd),.command_valid(out_valid),.command_ready(out_ready),.decoder_error(error));
 function automatic logic [15:0] crc_step(input logic [15:0] crc,input logic[7:0] b);
  logic[15:0] n;n=crc^{b,8'b0};for(integer i=0;i<8;i++)n=n[15]?(n<<1)^16'h1021:n<<1;return n;
 endfunction
 task automatic send(input logic[7:0] b);
  @(negedge clk);data=b;valid=1;do @(posedge clk);while(!ready);@(negedge clk);valid=0;
 endtask
 task automatic restart;
  @(negedge clk);reset=1;valid=0;out_ready=0;repeat(4)@(negedge clk);reset=0;
 endtask
 task automatic packet(input integer op,input integer n,input bit corrupt);
  logic[15:0] crc;logic[7:0] header[5];header='{71,70,2,8'(op),8'(n)};crc=16'hffff;
  for(integer i=0;i<5;i++)begin send(header[i]);crc=crc_step(crc,header[i]);end
  for(integer i=0;i<n;i++)begin send(8'(i));crc=crc_step(crc,8'(i));end
  send(crc[15:8]);send(crc[7:0]^{7'b0,corrupt});
 endtask
 initial begin
  restart();packet(13,28,0);wait(out_valid);held=cmd;
  if(error || cmd.opcode!=GFX_CMD_DRAW_MESH_Q8 || cmd.payload[223:200]!=24'h191a1b)$fatal(1,"new packet decode");
  for(integer i=0;i<25;i++)if(cmd.payload[199-i*8-:8]!=8'(i))$fatal(1,"legacy matrix slice changed");
  repeat(5)begin @(negedge clk);if(!out_valid || cmd!==held)$fatal(1,"backpressure instability");end
  out_ready=1;@(negedge clk);out_ready=0;
  restart();packet(8,25,0);wait(out_valid);
  if(error || cmd.opcode!=GFX_CMD_DRAW_MESH || cmd.payload[223:200]!=0)$fatal(1,"legacy packet regression");
  restart();packet(13,28,1);repeat(5)@(negedge clk);if(!seen_error || out_valid)$fatal(1,"bad CRC accepted");
  restart();packet(13,27,0);repeat(5)@(negedge clk);if(!seen_error || out_valid)$fatal(1,"bad length accepted");
  $display("PASS gpu_fractional_decoder_tb");$finish;
 end
 initial begin #1000000;$fatal(1,"fractional decoder timeout");end
endmodule
