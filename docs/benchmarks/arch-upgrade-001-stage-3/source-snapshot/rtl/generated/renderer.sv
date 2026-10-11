`include "renderer_types.svh"
`include "triangle_setup_types.svh"
module renderer #(
    parameter int FRAME_WIDTH = 320,
    parameter int FRAME_HEIGHT = 240,
`ifdef SOC_GPU_SETUP_OVERLAP
    parameter int SETUP_OVERLAP = 1
`else
    parameter int SETUP_OVERLAP = 0
`endif
) (
    input logic clk,
    input logic reset,
    input triangle_data_t triangle_data,
    input logic triangle_valid,
    output logic triangle_ready,
    output logic raster_write,
    output logic [9:0] raster_x,
    output logic [8:0] raster_y,
    output logic [7:0] raster_color,
    output logic depth_read_enable,
    output logic [9:0] depth_read_x,
    output logic [8:0] depth_read_y,
    input logic [7:0] depth_read_value,
    input logic depth_read_valid,
    output logic depth_write_enable,
    output logic [9:0] depth_write_x,
    output logic [8:0] depth_write_y,
    output logic [7:0] depth_write_value,
    output logic busy,
    output logic bounding_box_pixel,
    output logic pixel_inside,
    output logic depth_rejected,
    output logic pixel_written
);


    // Public diagnostic state keeps existing replay hooks compatible.
    // synthesis translate_off
    logic [2:0] state;
    wire setup_work, setup_blocked, raster_wait, setup_raster_overlap;
    wire [1:0] setup_queue_count;
    // synthesis translate_on
    generate if (!SETUP_OVERLAP) begin : serial
        renderer_serial #(.FRAME_WIDTH(FRAME_WIDTH), .FRAME_HEIGHT(FRAME_HEIGHT)) core(.*);
        // synthesis translate_off
        assign state = core.state;
        assign setup_work = (core.state>=1 && core.state<=5);
        assign setup_blocked = 0;
        assign raster_wait = setup_work;
        assign setup_raster_overlap = 0;
        assign setup_queue_count = 0;
        // synthesis translate_on
    end else begin : overlap
        renderer_overlap #(.FRAME_WIDTH(FRAME_WIDTH), .FRAME_HEIGHT(FRAME_HEIGHT)) core(.*);
        // synthesis translate_off
        assign state = core.state;
        assign setup_work = core.setup_busy && !core.produced_valid;
        assign setup_blocked = core.produced_valid && !core.produced_ready;
        assign raster_wait = core.state==0 && core.count==0 && core.setup_busy;
        assign setup_raster_overlap = core.state==6 && setup_work;
        assign setup_queue_count = core.count;
        // synthesis translate_on
    end endgenerate
endmodule
