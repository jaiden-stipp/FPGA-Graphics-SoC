`timescale 1ns/1ps
`include "renderer_types.svh"
module depth_banding_tb;
 logic clk=0,reset=1,triangle_valid=0,triangle_ready,raster_write;
 triangle_data_t triangle_data;
 logic [9:0] raster_x,depth_read_x,depth_write_x;
 logic [8:0] raster_y,depth_read_y,depth_write_y;
 logic [7:0] raster_color,depth_read_value=0,depth_write_value;
 logic depth_read_enable,depth_read_valid=0,depth_write_enable,busy;
 logic [7:0] depths[0:76799],colors[0:76799];
 integer i,first_pixels=0,second_pixels=0,fd;
 always #10 clk=~clk;
 renderer dut(.clk(clk),.reset(reset),.triangle_data(triangle_data),.triangle_valid(triangle_valid),.triangle_ready(triangle_ready),
 .raster_write(raster_write),.raster_x(raster_x),.raster_y(raster_y),.raster_color(raster_color),
 .depth_read_enable(depth_read_enable),.depth_read_x(depth_read_x),.depth_read_y(depth_read_y),.depth_read_value(depth_read_value),.depth_read_valid(depth_read_valid),
 .depth_write_enable(depth_write_enable),.depth_write_x(depth_write_x),.depth_write_y(depth_write_y),.depth_write_value(depth_write_value),.busy(busy),.bounding_box_pixel(),.pixel_inside(),.depth_rejected(),.pixel_written());
 always @(posedge clk) begin
  depth_read_valid<=!reset && depth_read_enable;
  if(depth_read_enable)depth_read_value<=depths[depth_read_y*320+depth_read_x];
  if(depth_write_enable)depths[depth_write_y*320+depth_write_x]<=depth_write_value;
  if(raster_write)begin
   colors[raster_y*320+raster_x]<=raster_color;
   if(raster_color==1)first_pixels=first_pixels+1;else second_pixels=second_pixels+1;
  end
 end
 task automatic send(input integer rotated);
  while(!triangle_ready)@(negedge clk);
  triangle_data='0;
  if(!rotated)begin
   triangle_data.x0=20;triangle_data.y0=20;triangle_data.z0=10;
   triangle_data.x1=300;triangle_data.y1=40;triangle_data.z1=15;
   triangle_data.x2=40;triangle_data.y2=220;triangle_data.z2=30;
  end else begin
   triangle_data.x0=40;triangle_data.y0=220;triangle_data.z0=30;
   triangle_data.x1=20;triangle_data.y1=20;triangle_data.z1=10;
   triangle_data.x2=300;triangle_data.y2=40;triangle_data.z2=15;
  end
  triangle_data.color=rotated?2:1;triangle_valid=1;
  @(negedge clk);triangle_valid=0;
  while(!triangle_ready)@(negedge clk);
 endtask
 initial begin
  triangle_data='0;
  for(i=0;i<76800;i=i+1)begin depths[i]=0;colors[i]=0;end
  repeat(3)@(negedge clk);reset=0;@(negedge clk);
  send(0);send(1);
  $display("Identical coplanar triangle, cyclic vertex order: first writes=%0d second writes=%0d",first_pixels,second_pixels);
  if(second_pixels==0)$fatal(1,"Expected to reproduce anchor-dependent depth banding");
  fd=$fopen("depth-banding.ppm","w");$fdisplay(fd,"P3\n320 240\n255");
  for(i=0;i<76800;i=i+1)case(colors[i])
   0:$fdisplay(fd,"100 170 230");1:$fdisplay(fd,"212 207 190");2:$fdisplay(fd,"55 110 37");
  endcase
  $fclose(fd);$finish;
 end
 initial begin #5000000;$fatal(1,"timeout");end
endmodule
