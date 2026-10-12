`ifndef TRIANGLE_SETUP_TYPES_SVH
`define TRIANGLE_SETUP_TYPES_SVH
// Internal setup-record v1. A skip token preserves empty-triangle ordering.
typedef struct packed {
    logic skip, positive_area;
    logic [9:0] min_x, max_x;
    logic [8:0] min_y, max_y;
    logic [7:0] color, minimum_depth, maximum_depth;
    logic signed [21:0] edge_01, edge_12, edge_20;
    logic signed [21:0] step_x_01, step_x_12, step_x_20;
    logic signed [21:0] step_y_01, step_y_12, step_y_20;
    logic signed [31:0] depth_step_x, depth_step_y;
    logic signed [35:0] depth_start;
} triangle_setup_record_t;
`endif
