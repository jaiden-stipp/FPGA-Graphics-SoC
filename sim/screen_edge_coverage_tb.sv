`timescale 1ns/1ps
`include "renderer_types.svh"
// Exercise the unchanged GPU projection, clipping, rasterizer and depth gate.
module screen_edge_coverage_tb;
    logic clk=0,reset=1,in_valid=0,in_ready,out_valid,out_ready,busy;
    always #10 clk=~clk;
    projection_config_t projection;
    triangle_3d_t in_data;
    triangle_data_t out_data;
    logic read_enable,read_valid=0,write_enable,raster_write,render_busy;
    logic [9:0] read_x,write_x,raster_x;
    logic [8:0] read_y,write_y,raster_y;
    logic [7:0] write_depth,color;
    bit coverage[0:76799];
    integer written,missing,case_number;
    transform_3d_pipeline transform(
        .clk(clk),.reset(reset),.projection(projection),.in_data(in_data),.in_valid(in_valid),.in_ready(in_ready),
        .out_data(out_data),.out_valid(out_valid),.out_ready(out_ready),.busy(busy),.triangle_clipped(),.triangle_culled());
    renderer raster(
        .clk(clk),.reset(reset),.triangle_data(out_data),.triangle_valid(out_valid),.triangle_ready(out_ready),
        .raster_write(raster_write),.raster_x(raster_x),.raster_y(raster_y),.raster_color(color),
        .depth_read_enable(read_enable),.depth_read_x(read_x),.depth_read_y(read_y),
        .depth_read_value(8'd0),.depth_read_valid(read_valid),.depth_write_enable(write_enable),
        .depth_write_x(write_x),.depth_write_y(write_y),.depth_write_value(write_depth),.busy(render_busy),
        .bounding_box_pixel(),.pixel_inside(),.depth_rejected(),.pixel_written());
    always @(posedge clk) begin
        read_valid<=read_enable;
        if(raster_write)begin
            if(raster_x>=320 || raster_y>=240)$fatal(1,"out-of-screen write");
            coverage[integer'(raster_y)*320+integer'(raster_x)]=1;
            written++;
        end
    end
    task automatic full_screen(input integer depth);
        for(integer i=0;i<76800;i++)coverage[i]=0;
        written=0;
        while(!in_ready)@(negedge clk);
        in_data='0;
        in_data.x0=-4000;in_data.y0=-4000;in_data.z0=depth;
        in_data.x1=0;in_data.y1=8000;in_data.z1=depth;
        in_data.x2=4000;in_data.y2=-4000;in_data.z2=depth;in_data.color=8'h42;
        in_valid=1;@(negedge clk);in_valid=0;
        while(busy || render_busy || out_valid)@(negedge clk);
        repeat(3)@(negedge clk);
        missing=0;
        for(integer i=0;i<76800;i++)if(!coverage[i])missing++;
        $display("EDGE_CASE depth=%0d unique_pixels=%0d missing=%0d",depth,76800-missing,missing);
        if(missing)$fatal(1,"full-screen triangle lost pixels");
    endtask
    initial begin
        in_data='0;projection='{16'sd256,16'sd256,16'sd160,16'sd120,16'sd257};
        repeat(4)@(negedge clk);reset=0;
        full_screen(512);full_screen(1024);full_screen(2048);
        $display("PASS screen_edge_coverage_tb");$finish;
    end
    initial begin #20000000;$fatal(1,"edge coverage timeout");end
endmodule
