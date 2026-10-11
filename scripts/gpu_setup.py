"""Split the validated rasterizer without replacing its arithmetic conventions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate(raster, replace_once, write):
    dest = ROOT / 'rtl/generated'
    # Independent serial reference remains selectable in the same build.
    write(dest / 'renderer_serial.sv', replace_once(raster, 'module renderer #(', 'module renderer_serial #('))
    types = '''`ifndef TRIANGLE_SETUP_TYPES_SVH
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
'''
    write(dest / 'triangle_setup_types.svh', types)

    # Extract the original setup registers, functions, combinational math and
    # sequential setup states. Anchor checks fail if the pinned source changes.
    declarations = raster.split('    logic [9:0] v0_x', 1)[1].split('    function automatic [9:0] min3_x', 1)[0]
    functions = raster.split('    function automatic [9:0] min3_x', 1)[1].split('    depth_test_stage depth_test', 1)[0]
    math = raster.split('    always_comb begin\n        raw_min_x', 1)[1].split('    always_comb begin\n        if (triangle_area', 1)[0]
    clamp = math.index('        if (current_depth <')
    math = math[:clamp] + '    end\n\n'
    sequential = raster.split('    always_ff @(posedge clk or posedge reset) begin', 1)[1]
    sequential = sequential[:sequential.index('                RASTERIZE: begin')] + '''                OUTPUT: begin
                    if (record_ready) state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
'''
    sequential = replace_once(sequential, 'if (triangle_valid) begin', 'if (triangle_valid && triangle_ready) begin\n                        record_data <= \'0;')
    sequential = replace_once(sequential, '                        state <= IDLE;', "                        record_data.skip <= 1'b1;\n                        state <= OUTPUT;")
    # Store the accepted setup quantities once; raster cannot see mutable
    # producer vertices, bounds, winding or extrema from the next triangle.
    fields = {'min_x': 'clipped_min_x', 'max_x': 'clipped_max_x',
              'min_y': 'clipped_min_y', 'max_y': 'clipped_max_y',
              'color': 'active_color', 'minimum_depth': 'minimum_depth',
              'maximum_depth': 'maximum_depth', 'positive_area': '(triangle_area > 0)'}
    for edge, a, b in [('01', 'v0', 'v1'), ('12', 'v1', 'v2'), ('20', 'v2', 'v0')]:
        fields['edge_' + edge] = f'edge_value({a}_x, {a}_y, {b}_x, {b}_y, clipped_min_x, clipped_min_y)'
        fields['step_x_' + edge] = f'edge_step_x({a}_y, {b}_y)'
        fields['step_y_' + edge] = f'edge_step_y({a}_x, {b}_x)'
    assignments = ''.join(f'                        record_data.{name} <= {expr};\n' for name, expr in fields.items())
    sequential = replace_once(sequential, '                        current_x <= clipped_min_x;', assignments + '                        current_x <= clipped_min_x;')
    sequential = replace_once(sequential, '                    state <= RASTERIZE;', '''                    record_data.depth_step_x <= depth_step_x;
                    record_data.depth_step_y <= depth_step_y;
                    record_data.depth_start <= setup_base_depth + depth_start_x + depth_start_y;
                    state <= OUTPUT;''')
    sequential = replace_once(sequential, '            state <= IDLE;', "            state <= IDLE;\n            record_data <= '0;")
    setup = '''`include "renderer_types.svh"
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
    logic [9:0] v0_x''' + declarations + '    function automatic [9:0] min3_x' + functions + '    always_comb begin\n        raw_min_x' + math + '    always_ff @(posedge clk or posedge reset) begin' + sequential
    write(dest / 'triangle_setup_engine.sv', setup)

    # Consumer uses the same raster increments and depth-test latency as serial.
    ports = raster.split('module renderer #(', 1)[1].split('    localparam int LAST_X', 1)[0]
    ports = replace_once(ports, '    parameter int FRAME_HEIGHT = 240', '''    parameter int FRAME_HEIGHT = 240,
`ifdef SOC_GPU_SETUP_OVERLAP
    parameter int SETUP_OVERLAP = 1
`else
    parameter int SETUP_OVERLAP = 0
`endif''')
    wrapper = '''`include "renderer_types.svh"
`include "triangle_setup_types.svh"
module renderer #(''' + ports + '''
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
'''
    write(dest / 'renderer.sv', wrapper)
    consumer_ports = raster.split('module renderer #(', 1)[1].split('    localparam int LAST_X', 1)[0]
    depth_test = raster.split('    depth_test_stage depth_test', 1)[1].split('    always_comb begin', 1)[0]
    traversal = raster.split('                RASTERIZE: begin', 1)[1].split('                default: state <= IDLE;', 1)[0]
    traversal = traversal.replace('clipped_max_x', 'active.max_x').replace('clipped_max_y', 'active.max_y').replace('clipped_min_x', 'active.min_x')
    consumer = '''`include "renderer_types.svh"
`include "triangle_setup_types.svh"
module renderer_overlap #(''' + consumer_ports + '''
    typedef enum logic [2:0] {IDLE=0, RASTERIZE=6, DRAIN=7} raster_state_t;
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
    depth_test_stage depth_test''' + depth_test + '''
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
            RASTERIZE: begin''' + traversal + '''
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
'''
    write(dest / 'renderer_overlap.sv', consumer)

    pipeline = (dest / 'graphics_pipeline.sv').read_text()
    pipeline = replace_once(pipeline, 'triangle_fifo_empty && !view_busy && !transform_busy &&\n                           renderer_triangle_ready', 'triangle_fifo_empty && !view_busy && !transform_busy &&\n                           !renderer_busy')
    write(dest / 'graphics_pipeline.sv', pipeline)
