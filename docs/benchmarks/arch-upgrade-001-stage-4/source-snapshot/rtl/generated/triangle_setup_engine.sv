`include "renderer_types.svh"
`include "triangle_setup_types.svh"
module triangle_setup_engine #(
    parameter int FRAME_WIDTH=320, FRAME_HEIGHT=240
)(
    input logic clk, reset,
    input triangle_data_t triangle_data,
    input logic triangle_valid,
    output logic triangle_ready,
    output triangle_setup_record_t record_data,
    output logic record_valid,
    input logic record_ready,
    output logic busy
);
    localparam int LAST_X=FRAME_WIDTH-1, LAST_Y=FRAME_HEIGHT-1;
    typedef enum logic [2:0] {IDLE, SETUP, SETUP_DIVIDE_START,
        SETUP_DIVIDE_WAIT, SETUP_DEPTH_PRODUCTS, SETUP_DEPTH_SUM, OUTPUT} setup_state_t;
    setup_state_t state;
    assign triangle_ready = (state == IDLE) && !reset;
    assign record_valid = (state == OUTPUT) && !reset;
    assign busy = (state != IDLE);
    logic [9:0] v0_x, v1_x, v2_x;
    logic [8:0] v0_y, v1_y, v2_y;
    logic [7:0] v0_depth, v1_depth, v2_depth;
    logic [7:0] active_color;
    logic [7:0] minimum_depth, maximum_depth;

    logic [9:0] raw_min_x, raw_max_x, clipped_min_x, clipped_max_x;
    logic [8:0] raw_min_y, raw_max_y, clipped_min_y, clipped_max_y;
    logic bounding_box_valid;

    logic signed [21:0] triangle_area;
    logic signed [21:0] standard_area;
    logic signed [21:0] edge_01;
    logic signed [21:0] edge_12;
    logic signed [21:0] edge_20;
    logic signed [21:0] row_edge_01;
    logic signed [21:0] row_edge_12;
    logic signed [21:0] row_edge_20;
    logic signed [21:0] step_x_01;
    logic signed [21:0] step_x_12;
    logic signed [21:0] step_x_20;
    logic signed [21:0] step_y_01;
    logic signed [21:0] step_y_12;
    logic signed [21:0] step_y_20;

    logic signed [11:0] depth_dx1;
    logic signed [10:0] depth_dy1;
    logic signed [11:0] depth_dx2;
    logic signed [10:0] depth_dy2;
    logic signed [16:0] depth_f0;
    logic signed [16:0] depth_f1;
    logic signed [16:0] depth_f2;
    logic signed [31:0] depth_dx_numerator;
    logic signed [31:0] depth_dy_numerator;
    logic signed [31:0] depth_step_x;
    logic signed [31:0] depth_step_y;
    logic depth_divide_start;
    logic depth_dx_done;
    logic depth_dy_done;
    logic signed [31:0] depth_dx_quotient;
    logic signed [31:0] depth_dy_quotient;
    logic signed [11:0] depth_offset_x;
    logic signed [10:0] depth_offset_y;
    logic signed [11:0] setup_offset_x;
    logic signed [10:0] setup_offset_y;
    logic signed [35:0] setup_base_depth;
    logic signed [35:0] depth_start_x;
    logic signed [35:0] depth_start_y;
    logic signed [35:0] current_depth;
    logic signed [35:0] row_depth;

    logic [9:0] current_x;
    logic [8:0] current_y;
    logic current_pixel_inside;

    logic [7:0] current_depth_byte;
    logic depth_test_busy;

    function automatic [9:0] min3_x(
        input logic [9:0] a,
        input logic [9:0] b,
        input logic [9:0] c
    );
        begin
            min3_x = (a < b) ? a : b;
            min3_x = (min3_x < c) ? min3_x : c;
        end
    endfunction

    function automatic [8:0] min3_y(
        input logic [8:0] a,
        input logic [8:0] b,
        input logic [8:0] c
    );
        begin
            min3_y = (a < b) ? a : b;
            min3_y = (min3_y < c) ? min3_y : c;
        end
    endfunction

    function automatic [9:0] max3_x(
        input logic [9:0] a,
        input logic [9:0] b,
        input logic [9:0] c
    );
        begin
            max3_x = (a > b) ? a : b;
            max3_x = (max3_x > c) ? max3_x : c;
        end
    endfunction

    function automatic [8:0] max3_y(
        input logic [8:0] a,
        input logic [8:0] b,
        input logic [8:0] c
    );
        begin
            max3_y = (a > b) ? a : b;
            max3_y = (max3_y > c) ? max3_y : c;
        end
    endfunction

    function automatic logic signed [21:0] edge_value(
        input logic [9:0] ax,
        input logic [8:0] ay,
        input logic [9:0] bx,
        input logic [8:0] by,
        input logic [9:0] px,
        input logic [8:0] py
    );
        logic signed [10:0] dx;
        logic signed [9:0] dy;
        logic signed [10:0] x_offset;
        logic signed [9:0] y_offset;
        logic signed [21:0] x_term;
        logic signed [21:0] y_term;
        begin
            dx = $signed({1'b0, bx}) - $signed({1'b0, ax});
            dy = $signed({1'b0, by}) - $signed({1'b0, ay});
            x_offset = $signed({1'b0, px}) - $signed({1'b0, ax});
            y_offset = $signed({1'b0, py}) - $signed({1'b0, ay});
            x_term = x_offset * dy;
            y_term = y_offset * dx;
            edge_value = x_term - y_term;
        end
    endfunction

    function automatic logic signed [21:0] edge_step_x(
        input logic [8:0] ay,
        input logic [8:0] by
    );
        begin
            edge_step_x = $signed({1'b0, by}) - $signed({1'b0, ay});
        end
    endfunction

    function automatic logic signed [21:0] edge_step_y(
        input logic [9:0] ax,
        input logic [9:0] bx
    );
        begin
            edge_step_y = $signed({1'b0, ax}) - $signed({1'b0, bx});
        end
    endfunction

    iterative_signed_divider #(
        .NUMERATOR_WIDTH(32),
        .DENOMINATOR_WIDTH(22)
    ) depth_dx_divider (
        .clk(clk),
        .reset(reset),
        .start(depth_divide_start),
        .numerator(depth_dx_numerator),
        .denominator(standard_area),
        .busy(),
        .done(depth_dx_done),
        .quotient(depth_dx_quotient)
    );

    iterative_signed_divider #(
        .NUMERATOR_WIDTH(32),
        .DENOMINATOR_WIDTH(22)
    ) depth_dy_divider (
        .clk(clk),
        .reset(reset),
        .start(depth_divide_start),
        .numerator(depth_dy_numerator),
        .denominator(standard_area),
        .busy(),
        .done(depth_dy_done),
        .quotient(depth_dy_quotient)
    );

    always_comb begin
        raw_min_x = min3_x(v0_x, v1_x, v2_x);
        raw_max_x = max3_x(v0_x, v1_x, v2_x);
        raw_min_y = min3_y(v0_y, v1_y, v2_y);
        raw_max_y = max3_y(v0_y, v1_y, v2_y);
        clipped_min_x = raw_min_x;
        clipped_min_y = raw_min_y;
        clipped_max_x = (raw_max_x > LAST_X) ? LAST_X[9:0] : raw_max_x;
        clipped_max_y = (raw_max_y > LAST_Y) ? LAST_Y[8:0] : raw_max_y;
        bounding_box_valid = (raw_min_x <= LAST_X) && (raw_min_y <= LAST_Y);
        triangle_area = edge_value(v0_x, v0_y, v1_x, v1_y, v2_x, v2_y);
        standard_area = -triangle_area;
        depth_dx1 = $signed({1'b0, v1_x}) - $signed({1'b0, v0_x});
        depth_dy1 = $signed({1'b0, v1_y}) - $signed({1'b0, v0_y});
        depth_dx2 = $signed({1'b0, v2_x}) - $signed({1'b0, v0_x});
        depth_dy2 = $signed({1'b0, v2_y}) - $signed({1'b0, v0_y});
        minimum_depth = v0_depth < v1_depth ? v0_depth : v1_depth;
        minimum_depth = minimum_depth < v2_depth ? minimum_depth : v2_depth;
        maximum_depth = v0_depth > v1_depth ? v0_depth : v1_depth;
        maximum_depth = maximum_depth > v2_depth ? maximum_depth : v2_depth;
        depth_f0 = $signed({1'b0, v0_depth, 8'b0});
        depth_f1 = $signed({1'b0, v1_depth, 8'b0});
        depth_f2 = $signed({1'b0, v2_depth, 8'b0});
        depth_dx_numerator = (depth_f1 - depth_f0) * depth_dy2 -
                             (depth_f2 - depth_f0) * depth_dy1;
        depth_dy_numerator = depth_dx1 * (depth_f2 - depth_f0) -
                             depth_dx2 * (depth_f1 - depth_f0);
        depth_offset_x = $signed({1'b0, clipped_min_x}) - $signed({1'b0, v0_x});
        depth_offset_y = $signed({1'b0, clipped_min_y}) - $signed({1'b0, v0_y});
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state <= IDLE;
            record_data <= '0;
            v0_x <= '0;
            v0_y <= '0;
            v1_x <= '0;
            v1_y <= '0;
            v2_x <= '0;
            v2_y <= '0;
            v0_depth <= '0;
            v1_depth <= '0;
            v2_depth <= '0;
            active_color <= '0;
            current_x <= '0;
            current_y <= '0;
            edge_01 <= '0;
            edge_12 <= '0;
            edge_20 <= '0;
            row_edge_01 <= '0;
            row_edge_12 <= '0;
            row_edge_20 <= '0;
            step_x_01 <= '0;
            step_x_12 <= '0;
            step_x_20 <= '0;
            step_y_01 <= '0;
            step_y_12 <= '0;
            step_y_20 <= '0;
            depth_step_x <= '0;
            depth_step_y <= '0;
            setup_offset_x <= '0;
            setup_offset_y <= '0;
            setup_base_depth <= '0;
            depth_start_x <= '0;
            depth_start_y <= '0;
            current_depth <= '0;
            row_depth <= '0;
            depth_divide_start <= 1'b0;
        end else begin
            depth_divide_start <= 1'b0;

            case (state)
                IDLE: begin
                    if (triangle_valid && triangle_ready) begin
                        record_data <= '0;
                        v0_x <= triangle_data.x0;
                        v0_y <= triangle_data.y0;
                        v1_x <= triangle_data.x1;
                        v1_y <= triangle_data.y1;
                        v2_x <= triangle_data.x2;
                        v2_y <= triangle_data.y2;
                        v0_depth <= triangle_data.z0;
                        v1_depth <= triangle_data.z1;
                        v2_depth <= triangle_data.z2;
                        active_color <= triangle_data.color;
                        state <= SETUP;
                    end
                end

                SETUP: begin
                    if (!bounding_box_valid || (triangle_area == 0)) begin
                        record_data.skip <= 1'b1;
                        state <= OUTPUT;
                    end else begin
                        record_data.min_x <= clipped_min_x;
                        record_data.max_x <= clipped_max_x;
                        record_data.min_y <= clipped_min_y;
                        record_data.max_y <= clipped_max_y;
                        record_data.color <= active_color;
                        record_data.minimum_depth <= minimum_depth;
                        record_data.maximum_depth <= maximum_depth;
                        record_data.positive_area <= (triangle_area > 0);
                        record_data.edge_01 <= edge_value(v0_x, v0_y, v1_x, v1_y, clipped_min_x, clipped_min_y);
                        record_data.step_x_01 <= edge_step_x(v0_y, v1_y);
                        record_data.step_y_01 <= edge_step_y(v0_x, v1_x);
                        record_data.edge_12 <= edge_value(v1_x, v1_y, v2_x, v2_y, clipped_min_x, clipped_min_y);
                        record_data.step_x_12 <= edge_step_x(v1_y, v2_y);
                        record_data.step_y_12 <= edge_step_y(v1_x, v2_x);
                        record_data.edge_20 <= edge_value(v2_x, v2_y, v0_x, v0_y, clipped_min_x, clipped_min_y);
                        record_data.step_x_20 <= edge_step_x(v2_y, v0_y);
                        record_data.step_y_20 <= edge_step_y(v2_x, v0_x);
                        current_x <= clipped_min_x;
                        current_y <= clipped_min_y;
                        edge_01 <= edge_value(v0_x, v0_y, v1_x, v1_y,
                                              clipped_min_x, clipped_min_y);
                        edge_12 <= edge_value(v1_x, v1_y, v2_x, v2_y,
                                              clipped_min_x, clipped_min_y);
                        edge_20 <= edge_value(v2_x, v2_y, v0_x, v0_y,
                                              clipped_min_x, clipped_min_y);
                        row_edge_01 <= edge_value(v0_x, v0_y, v1_x, v1_y,
                                                  clipped_min_x, clipped_min_y);
                        row_edge_12 <= edge_value(v1_x, v1_y, v2_x, v2_y,
                                                  clipped_min_x, clipped_min_y);
                        row_edge_20 <= edge_value(v2_x, v2_y, v0_x, v0_y,
                                                  clipped_min_x, clipped_min_y);
                        step_x_01 <= edge_step_x(v0_y, v1_y);
                        step_x_12 <= edge_step_x(v1_y, v2_y);
                        step_x_20 <= edge_step_x(v2_y, v0_y);
                        step_y_01 <= edge_step_y(v0_x, v1_x);
                        step_y_12 <= edge_step_y(v1_x, v2_x);
                        step_y_20 <= edge_step_y(v2_x, v0_x);
                        setup_offset_x <= depth_offset_x;
                        setup_offset_y <= depth_offset_y;
                        setup_base_depth <= $signed({1'b0, v0_depth, 8'b0});
                        state <= SETUP_DIVIDE_START;
                    end
                end

                SETUP_DIVIDE_START: begin
                    depth_divide_start <= 1'b1;
                    state <= SETUP_DIVIDE_WAIT;
                end

                SETUP_DIVIDE_WAIT: begin
                    if (depth_dx_done && depth_dy_done) begin
                        depth_step_x <= depth_dx_quotient;
                        depth_step_y <= depth_dy_quotient;
                        state <= SETUP_DEPTH_PRODUCTS;
                    end
                end

                SETUP_DEPTH_PRODUCTS: begin
                    depth_start_x <= depth_step_x * setup_offset_x;
                    depth_start_y <= depth_step_y * setup_offset_y;
                    state <= SETUP_DEPTH_SUM;
                end

                SETUP_DEPTH_SUM: begin
                    current_depth <= setup_base_depth + depth_start_x + depth_start_y;
                    row_depth <= setup_base_depth + depth_start_x + depth_start_y;
                    record_data.depth_step_x <= depth_step_x;
                    record_data.depth_step_y <= depth_step_y;
                    record_data.depth_start <= setup_base_depth + depth_start_x + depth_start_y;
                    state <= OUTPUT;
                end

                OUTPUT: begin
                    if (record_ready) state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
