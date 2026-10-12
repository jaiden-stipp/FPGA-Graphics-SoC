`include "renderer_types.svh"
`include "triangle_setup_types.svh"
module renderer_overlap #(
    parameter int FRAME_WIDTH = 320,
    parameter int FRAME_HEIGHT = 240
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


    typedef enum logic [2:0] {IDLE=3'd0, RASTERIZE=3'd6, DRAIN=3'd7} raster_state_t;
    raster_state_t state;
    triangle_setup_record_t produced, active, records[0:1];
    logic produced_valid, produced_ready, setup_busy;
    logic read_ptr, write_ptr;
    logic [1:0] count;
    wire push = produced_valid && produced_ready;
    // Conservative full handling: no write to a full queue even during a pop.
    wire pop = (state == IDLE) && (count != 0) && !reset;
    assign produced_ready = (count < 2) && !reset;
    triangle_setup_engine #(.FRAME_WIDTH(FRAME_WIDTH),.FRAME_HEIGHT(FRAME_HEIGHT)) setup_engine(
        .clk(clk),.reset(reset),.triangle_data(triangle_data),.triangle_valid(triangle_valid),
        .triangle_ready(triangle_ready),.record_data(produced),.record_valid(produced_valid),
        .record_ready(produced_ready),.busy(setup_busy));
    // Stable registered queue records; producer cannot overwrite active data.
    always_ff @(posedge clk or posedge reset) begin
        if(reset) begin count<=0; read_ptr<=0; write_ptr<=0; end
        else begin
            if(push) begin records[write_ptr]<=produced; write_ptr<=!write_ptr; end
            if(pop) read_ptr<=!read_ptr;
            case({push,pop})
                2'b10:count<=count+1'b1;
                2'b01:count<=count-1'b1;
                default:begin end
            endcase
        end
    end
    logic [9:0] current_x;
    logic [8:0] current_y;
    logic signed [21:0] edge_01,edge_12,edge_20,row_edge_01,row_edge_12,row_edge_20;
    wire signed [21:0] step_x_01=active.step_x_01,step_x_12=active.step_x_12,step_x_20=active.step_x_20;
    wire signed [21:0] step_y_01=active.step_y_01,step_y_12=active.step_y_12,step_y_20=active.step_y_20;
    wire signed [31:0] depth_step_x=active.depth_step_x,depth_step_y=active.depth_step_y;
    wire [7:0] active_color=active.color;
    logic signed [35:0] current_depth,row_depth;
    logic [7:0] current_depth_byte;
    logic current_pixel_inside,depth_test_busy;
    assign busy = setup_busy || (count != 0) || (state != IDLE) || depth_test_busy;
    assign bounding_box_pixel = (state == RASTERIZE);
    assign pixel_inside = (state == RASTERIZE) && current_pixel_inside;
    always_comb begin
        if(active.positive_area)
            current_pixel_inside=(edge_01>=0)&&(edge_12>=0)&&(edge_20>=0);
        else current_pixel_inside=(edge_01<=0)&&(edge_12<=0)&&(edge_20<=0);
        if(current_depth < $signed({1'b0,active.minimum_depth,8'b0}))
            current_depth_byte=active.minimum_depth;
        else if(current_depth > $signed({1'b0,active.maximum_depth,8'b0}))
            current_depth_byte=active.maximum_depth;
        else current_depth_byte=current_depth[15:8];
    end
    depth_test_stage depth_test (
        .clk(clk),
        .reset(reset),
        .candidate_valid((state == RASTERIZE) && current_pixel_inside),
        .candidate_x(current_x),
        .candidate_y(current_y),
        .candidate_color(active_color),
        .candidate_depth(current_depth_byte),
        .depth_read_enable(depth_read_enable),
        .depth_read_x(depth_read_x),
        .depth_read_y(depth_read_y),
        .depth_read_value(depth_read_value),
        .depth_read_valid(depth_read_valid),
        .raster_write(raster_write),
        .raster_x(raster_x),
        .raster_y(raster_y),
        .raster_color(raster_color),
        .depth_write_enable(depth_write_enable),
        .depth_write_x(depth_write_x),
        .depth_write_y(depth_write_y),
        .depth_write_value(depth_write_value),
        .depth_rejected(depth_rejected),
        .pixel_written(pixel_written),
        .busy(depth_test_busy)
    );


    always_ff @(posedge clk or posedge reset) begin
        if(reset) begin
            state<=IDLE; active<='0; current_x<=0; current_y<=0;
            edge_01<=0;edge_12<=0;edge_20<=0;
            row_edge_01<=0;row_edge_12<=0;row_edge_20<=0;
            current_depth<=0;row_depth<=0;
        end else case(state)
            IDLE: if(pop) begin
                active<=records[read_ptr];
                current_x<=records[read_ptr].min_x;current_y<=records[read_ptr].min_y;
                edge_01<=records[read_ptr].edge_01;row_edge_01<=records[read_ptr].edge_01;
                edge_12<=records[read_ptr].edge_12;row_edge_12<=records[read_ptr].edge_12;
                edge_20<=records[read_ptr].edge_20;row_edge_20<=records[read_ptr].edge_20;
                current_depth<=records[read_ptr].depth_start;row_depth<=records[read_ptr].depth_start;
                if(!records[read_ptr].skip)state<=RASTERIZE;
            end
            RASTERIZE: begin
                    if (current_x == active.max_x) begin
                        if (current_y == active.max_y) begin
                            state <= DRAIN;
                        end else begin
                            current_x <= active.min_x;
                            current_y <= current_y + 1'b1;
                            row_edge_01 <= row_edge_01 + step_y_01;
                            row_edge_12 <= row_edge_12 + step_y_12;
                            row_edge_20 <= row_edge_20 + step_y_20;
                            edge_01 <= row_edge_01 + step_y_01;
                            edge_12 <= row_edge_12 + step_y_12;
                            edge_20 <= row_edge_20 + step_y_20;
                            row_depth <= row_depth + depth_step_y;
                            current_depth <= row_depth + depth_step_y;
                        end
                    end else begin
                        current_x <= current_x + 1'b1;
                        edge_01 <= edge_01 + step_x_01;
                        edge_12 <= edge_12 + step_x_12;
                        edge_20 <= edge_20 + step_x_20;
                        current_depth <= current_depth + depth_step_x;
                    end
                end

                DRAIN: begin
                    if (!depth_test_busy)
                        state <= IDLE;
                end


            default:state<=IDLE;
        endcase
    end
    // Simulation diagnostics never change the fitted datapath or MMIO ABI.
    // synthesis translate_off
    integer accepted=0,retired=0,max_queue=0,setup_active_cycles=0;
    integer setup_blocked_cycles=0,raster_wait_cycles=0,overlap_cycles=0;
    triangle_setup_record_t stalled_record;
    logic was_stalled=0;
    always @(posedge clk) begin
        if(reset)begin
            accepted=0;retired=0;max_queue=0;setup_active_cycles=0;
            setup_blocked_cycles=0;raster_wait_cycles=0;overlap_cycles=0;was_stalled=0;
        end else begin
            if(triangle_valid && triangle_ready)accepted++;
            if(pop)retired++;
            if(count>max_queue)max_queue=count;
            if(setup_busy)setup_active_cycles++;
            if(produced_valid && !produced_ready)setup_blocked_cycles++;
            if(state==IDLE && count==0 && setup_busy)raster_wait_cycles++;
            if(state==RASTERIZE && setup_busy)overlap_cycles++;
            if(was_stalled && produced!==stalled_record)$fatal(1,"unstable setup record");
            if(count>2 || (pop && count==0))$fatal(1,"setup queue bounds");
            stalled_record=produced;was_stalled=produced_valid && !produced_ready;
            if(!busy && !(triangle_valid && triangle_ready) && accepted!=retired)$fatal(1,"lost setup record");
        end
    end
    // synthesis translate_on
endmodule
