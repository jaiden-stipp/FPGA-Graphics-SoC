`timescale 1ns/1ps
`include "renderer_types.svh"
// An empty Z buffer must accept every covered pixel of a nonzero-depth face.
module depth_edge_coverage_tb #(parameter REQUIRE_COVERAGE=1);
    logic clk=0,reset=1,valid=0,ready,busy;
    always #10 clk=~clk;
    triangle_data_t data;
    logic read_enable,read_valid=0,write,inside_pixel,rejected;
    logic [9:0] read_x,write_x;
    logic [8:0] read_y,write_y;
    logic [7:0] write_depth;
    logic read_enable1,read_valid1=0,write1,inside_pixel1,rejected1;
    logic[7:0]write_depth1;
    integer covered=0,written=0,failed=0;
    renderer dut(.clk(clk),.reset(reset),.triangle_data(data),.triangle_valid(valid),.triangle_ready(ready),
        .raster_write(write),.raster_x(),.raster_y(),.raster_color(),
        .depth_read_enable(read_enable),.depth_read_x(read_x),.depth_read_y(read_y),
        .depth_read_value(8'd0),.depth_read_valid(read_valid),.depth_write_enable(),
        .depth_write_x(write_x),.depth_write_y(write_y),.depth_write_value(write_depth),.busy(busy),
        .bounding_box_pixel(),.pixel_inside(inside_pixel),.depth_rejected(rejected),.pixel_written(),
        .raster_write1(write1),.depth_write_value1(write_depth1),
        .depth_read_enable1(read_enable1),.depth_read_value1(8'd0),.depth_read_valid1(read_valid1),
        .pixel_inside1(inside_pixel1),.depth_rejected1(rejected1));
    always @(posedge clk)begin
        read_valid<=read_enable;read_valid1<=read_enable1;
        if(inside_pixel1)covered++;
        if(write1)begin
            written++;
            if(REQUIRE_COVERAGE && (write_depth1<2 || write_depth1>8))$fatal(1,"odd depth outside vertex bounds");
        end
        if(rejected1)failed++;
        if(inside_pixel)covered++;
        if(write)begin
            written++;
            if(REQUIRE_COVERAGE && (write_depth<2 || write_depth>8))$fatal(1,"depth outside vertex bounds");
        end
        if(rejected)failed++;
    end
    initial begin
        data='0;repeat(4)@(negedge clk);reset=0;
        while(!ready)@(negedge clk);
        data.x0=302;data.y0=234;data.z0=8;
        data.x1=249;data.y1=197;data.z1=3;
        data.x2=6;data.y2=133;data.z2=2;data.color=1;
        valid=1;@(negedge clk);valid=0;
        while(busy)@(negedge clk);repeat(3)@(negedge clk);
        $display("DEPTH_EDGE covered=%0d written=%0d rejected=%0d",covered,written,failed);
        if(REQUIRE_COVERAGE && (failed || written!=covered))$fatal(1,"valid distant triangle has background holes");
        $display("PASS depth_edge_coverage_tb");$finish;
    end
    initial begin #10000000;$fatal(1,"depth edge timeout");end
endmodule
