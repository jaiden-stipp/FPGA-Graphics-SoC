"""Generate optional adjacent-pixel raster and parity-banked memory adaptations.

Pinned upstream sources stay untouched. Stage 3 remains the default reference.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIXEL_EVENTS = ('bounding_box_pixel', 'pixel_inside', 'depth_rejected', 'pixel_written')
LANE_PORTS = '''
    output logic raster_write1,
    output logic [9:0] raster_x1,
    output logic [8:0] raster_y1,
    output logic [7:0] raster_color1,
    output logic depth_read_enable1,
    output logic [9:0] depth_read_x1,
    output logic [8:0] depth_read_y1,
    input logic [7:0] depth_read_value1,
    input logic depth_read_valid1,
    output logic depth_write_enable1,
    output logic [9:0] depth_write_x1,
    output logic [8:0] depth_write_y1,
    output logic [7:0] depth_write_value1,
    output logic bounding_box_pixel1, pixel_inside1, depth_rejected1, pixel_written1,
'''


def generate(replace_once, write):
    dest = ROOT / 'rtl/generated'
    upstream = ROOT / 'external/renderer/rtl'
    consumer = (dest / 'renderer_overlap.sv').read_text()
    dual = replace_once(consumer, 'module renderer_overlap #(', 'module renderer_dual #(')
    dual = replace_once(dual, '    output logic busy,', LANE_PORTS + '    output logic busy,')
    dual = replace_once(dual, 'logic current_pixel_inside,depth_test_busy;', '''logic current_pixel_inside,depth_test_busy,depth_test_busy1;
    wire [9:0] next_x = current_x + 10'd1;
    wire lane0_valid = current_x >= active.min_x && current_x <= active.max_x;
    wire lane1_valid = next_x >= active.min_x && next_x <= active.max_x;
    wire signed [21:0] lane1_edge_01 = edge_01 + step_x_01;
    wire signed [21:0] lane1_edge_12 = edge_12 + step_x_12;
    wire signed [21:0] lane1_edge_20 = edge_20 + step_x_20;
    wire signed [35:0] lane1_depth = current_depth + depth_step_x;
    logic lane1_inside;
    logic [7:0] lane1_depth_byte;
    assign bounding_box_pixel1 = state == RASTERIZE && lane1_valid;
    assign pixel_inside1 = state == RASTERIZE && lane1_valid && lane1_inside;
    always_comb begin
        if(active.positive_area)
            lane1_inside = lane1_edge_01>=0 && lane1_edge_12>=0 && lane1_edge_20>=0;
        else lane1_inside = lane1_edge_01<=0 && lane1_edge_12<=0 && lane1_edge_20<=0;
        if(lane1_depth < $signed({1'b0,active.minimum_depth,8'b0}))
            lane1_depth_byte = active.minimum_depth;
        else if(lane1_depth > $signed({1'b0,active.maximum_depth,8'b0}))
            lane1_depth_byte = active.maximum_depth;
        else lane1_depth_byte = lane1_depth[15:8];
    end''')
    dual = dual.replace('|| depth_test_busy;', '|| depth_test_busy || depth_test_busy1;')
    dual = replace_once(dual, 'assign bounding_box_pixel = (state == RASTERIZE);', 'assign bounding_box_pixel = (state == RASTERIZE) && lane0_valid;')
    dual = replace_once(dual, 'assign pixel_inside = (state == RASTERIZE) && current_pixel_inside;', 'assign pixel_inside = (state == RASTERIZE) && lane0_valid && current_pixel_inside;')
    start = dual.index('    depth_test_stage depth_test (')
    end = dual.index('    always_ff', start)
    depth = dual[start:end]
    depth = depth.replace('(state == RASTERIZE) && current_pixel_inside', '(state == RASTERIZE) && lane0_valid && current_pixel_inside')
    second = depth.replace('depth_test (', 'depth_test1 (')
    # Replace connected signal names, never the formal port names.
    names = ['raster_write','raster_x','raster_y','raster_color','depth_read_enable',
             'depth_read_x','depth_read_y','depth_read_value','depth_read_valid',
             'depth_write_enable','depth_write_x','depth_write_y','depth_write_value',
             'depth_rejected','pixel_written','depth_test_busy']
    for name in names:
        second = second.replace('('+name+')', '('+name+'1)')
    second = second.replace('lane0_valid && current_pixel_inside', 'lane1_valid && lane1_inside')
    second = second.replace('(current_x)', '(next_x)').replace('(current_depth_byte)', '(lane1_depth_byte)')
    dual = dual[:start] + depth + second + dual[end:]
    # Pair origin is even. Subtract one step on an odd left bound, with the
    # original edge/depth widths; lane 1 then reconstructs that first pixel.
    dual = dual.replace('current_x<=records[read_ptr].min_x;', "current_x<={records[read_ptr].min_x[9:1],1'b0};")
    for edge in ('01','12','20'):
        expr = f"records[read_ptr].edge_{edge} - (records[read_ptr].min_x[0] ? records[read_ptr].step_x_{edge} : 22'sd0)"
        dual = dual.replace(f'<=records[read_ptr].edge_{edge};', '<='+expr+';')
    expr = "records[read_ptr].depth_start - (records[read_ptr].min_x[0] ? {{4{records[read_ptr].depth_step_x[31]}},records[read_ptr].depth_step_x} : 36'sd0)"
    dual = dual.replace('<=records[read_ptr].depth_start;', '<='+expr+';')
    dual = dual.replace('current_x == active.max_x', 'next_x >= active.max_x')
    dual = dual.replace('current_x <= active.min_x;', "current_x <= {active.min_x[9:1],1'b0};")
    dual = dual.replace("current_x <= current_x + 1'b1;", "current_x <= current_x + 10'd2;")
    for edge in ('01','12','20'):
        dual = dual.replace(f'edge_{edge} + step_x_{edge};', f'edge_{edge} + step_x_{edge} + step_x_{edge};')
        dual = dual.replace(f'lane1_edge_{edge} = edge_{edge} + step_x_{edge} + step_x_{edge};', f'lane1_edge_{edge} = edge_{edge} + step_x_{edge};')
    dual = dual.replace('current_depth + depth_step_x;', 'current_depth + depth_step_x + depth_step_x;')
    # The preceding text replacement also touched the lane1 wire: restore it.
    dual = dual.replace('lane1_depth = current_depth + depth_step_x + depth_step_x;', 'lane1_depth = current_depth + depth_step_x;')
    dual = dual.replace('if (!depth_test_busy)', 'if (!depth_test_busy && !depth_test_busy1)')
    write(dest / 'renderer_dual.sv', dual)

    wrapper = (dest / 'renderer.sv').read_text()
    wrapper = replace_once(wrapper, '    output logic busy,', LANE_PORTS + '    output logic busy,')
    wrapper = replace_once(wrapper, '    generate if (!SETUP_OVERLAP)', '''`ifdef SOC_GPU_TWO_PIXEL_LANES
    renderer_dual #(.FRAME_WIDTH(FRAME_WIDTH),.FRAME_HEIGHT(FRAME_HEIGHT)) core(.*);
    // synthesis translate_off
    assign state = core.state;
    assign setup_work = core.setup_busy && !core.produced_valid;
    assign setup_blocked = core.produced_valid && !core.produced_ready;
    assign raster_wait = core.state==0 && core.count==0 && core.setup_busy;
    assign setup_raster_overlap = core.state==6 && setup_work;
    assign setup_queue_count = core.count;
    // synthesis translate_on
`else
    assign raster_write1=0, raster_x1=0, raster_y1=0, raster_color1=0;
    assign depth_read_enable1=0, depth_read_x1=0, depth_read_y1=0;
    assign depth_write_enable1=0, depth_write_x1=0, depth_write_y1=0, depth_write_value1=0;
    assign bounding_box_pixel1=0, pixel_inside1=0, depth_rejected1=0, pixel_written1=0;
    generate if (!SETUP_OVERLAP)''')
    wrapper = wrapper.replace('    end endgenerate\nendmodule', '    end endgenerate\n`endif\nendmodule')
    write(dest / 'renderer.sv', wrapper)

    # Original modules remain the single-lane branch of the same generated
    # interfaces, so old simulation probes and command ABI remain available.
    for name in ('zbuffer','framebuffer'):
        original = (upstream / 'memory' / (name+'.sv')).read_text()
        original = original.replace('module '+name, 'module '+name+'_single', 1)
        write(dest / (name+'_single.sv'), original)
    write(dest / 'pixel_bank_ram.sv', BANK_RAM)
    write(dest / 'zbuffer_banked.sv', DEPTH_BANKS)
    write(dest / 'framebuffer_banked.sv', COLOR_BANKS)
    vga = (upstream / 'video/vga_controller.sv').read_text()
    vga = replace_once(vga, '    input logic clear_request,', '''    input logic raster_write1,
    input logic [9:0] raster_x1,
    input logic [8:0] raster_y1,
    input logic [7:0] raster_color1,
    input  logic        clear_request,''')
    vga = vga.replace('    framebuffer #(', '''`ifdef SOC_GPU_TWO_PIXEL_LANES
    framebuffer_banked #(
`else
    framebuffer_single #(
`endif''')
    for page, select in ((0,'!write_page_raster'),(1,'write_page_raster')):
        anchor = f'        .raster_write(raster_write && {select}),'
        vga = replace_once(vga, anchor, anchor+f'''
`ifdef SOC_GPU_TWO_PIXEL_LANES
        .raster_write1(raster_write1 && {select}),
        .raster_x1(raster_x1),.raster_y1(raster_y1),.raster_color1(raster_color1),
`endif''')
    write(dest / 'vga_controller.sv', vga)
    pipeline = (dest / 'graphics_pipeline.sv').read_text()
    declarations = '''    logic raster_write1;
    logic [9:0] raster_x1,depth_read_x1,depth_write_x1;
    logic [8:0] raster_y1,depth_read_y1,depth_write_y1;
    logic [7:0] raster_color1,depth_read_value1,depth_write_value1;
    logic depth_read_enable1,depth_read_valid1,depth_write_enable1;
    logic bounding_box_pixel1,pixel_inside1,depth_rejected1,pixel_written1;
'''
    pipeline = replace_once(pipeline, '    logic pixel_clk;', declarations+'    logic pixel_clk;')
    connection = '''        .raster_write1(raster_write1),.raster_x1(raster_x1),
        .raster_y1(raster_y1),.raster_color1(raster_color1),
'''
    anchor = '        .raster_write(raster_write),'
    pipeline = pipeline.replace(anchor, anchor+'\n'+connection)
    anchor = '        .busy(renderer_busy),'
    extra = ''.join(f'        .{n}1({n}1),\n' for n in ('depth_read_enable','depth_read_x','depth_read_y','depth_read_value','depth_read_valid','depth_write_enable','depth_write_x','depth_write_y','depth_write_value')+PIXEL_EVENTS)
    pipeline = replace_once(pipeline, anchor, extra+anchor)
    # Only the counter instance gets sums; scalar lane events stay diagnostic.
    start = pipeline.index('    render_performance_counters performance_counters')
    end = pipeline.index('    zbuffer depth_memory', start)
    counters = pipeline[start:end]
    for n in PIXEL_EVENTS:
        counters = counters.replace(f'.{n}({n})', f'.{n}({{1\'b0,{n}}} + {{1\'b0,{n}1}})')
    pipeline = pipeline[:start]+counters+pipeline[end:]
    pipeline = replace_once(pipeline, '    zbuffer depth_memory (', '''`ifdef SOC_GPU_TWO_PIXEL_LANES
    zbuffer_banked depth_memory (
        .read_enable1(depth_read_enable1),.read_x1(depth_read_x1),.read_y1(depth_read_y1),
        .read_depth1(depth_read_value1),.read_valid1(depth_read_valid1),
        .write_enable1(depth_write_enable1),.write_x1(depth_write_x1),
        .write_y1(depth_write_y1),.write_depth1(depth_write_value1),
`else
    assign depth_read_value1=0,depth_read_valid1=0;
    zbuffer_single depth_memory (
`endif''')
    write(dest / 'graphics_pipeline.sv', pipeline)
    counters = (upstream / 'pipeline/render_performance_counters.sv').read_text()
    for n in PIXEL_EVENTS:
        counters = counters.replace('input logic '+n+',', 'input logic [1:0] '+n+',')
    for field,n in (('bounding_box_pixels','bounding_box_pixel'),('pixels_inside','pixel_inside'),('depth_rejected','depth_rejected'),('pixels_written','pixel_written')):
        counters = counters.replace(f'current_stats.{field} + 1\'b1', f'current_stats.{field} + {n}')
    write(dest / 'render_performance_counters.sv', counters)


BANK_RAM = '''// One synchronous read, one write. Parity banks retain original RAM latency.
module pixel_bank_ram #(parameter int WORDS=38400, ADDR_BITS=$clog2(WORDS))(
    input logic write_clk,read_clk,
    input logic [ADDR_BITS-1:0] write_address,read_address,
    input logic [7:0] write_data,
    input logic write_enable,read_enable,
    output wire [7:0] read_data
);
    altsyncram #(.operation_mode("DUAL_PORT"),.width_a(8),.width_b(8),
        .widthad_a(ADDR_BITS),.widthad_b(ADDR_BITS),.numwords_a(WORDS),.numwords_b(WORDS),
        .address_reg_b("CLOCK1"),.rdcontrol_reg_b("CLOCK1"),.outdata_reg_b("UNREGISTERED"),
        .ram_block_type("M9K"),.intended_device_family("Cyclone IV E"),
        .power_up_uninitialized("FALSE"),.read_during_write_mode_mixed_ports("DONT_CARE"),
        .lpm_type("altsyncram")) ram(
        .address_a(write_address),.address_b(read_address),.clock0(write_clk),.clock1(read_clk),
        .clocken0(1'b1),.clocken1(1'b1),.data_a(write_data),
        .rden_b(read_enable),.wren_a(write_enable),.q_b(read_data));
endmodule
'''

DEPTH_BANKS = '''// Each lane owns its X parity. Explicit same-edge forwarding avoids DONT_CARE.
module zbuffer_banked #(parameter int FRAME_WIDTH=320,FRAME_HEIGHT=240)(
    input logic reset,raster_clk,clear_request,output logic clear_busy,
    input logic read_enable, input logic [9:0] read_x,input logic [8:0] read_y,
    output wire [7:0] read_depth,output logic read_valid,
    input logic write_enable,input logic [9:0] write_x,input logic [8:0] write_y,
    input logic [7:0] write_depth,
    input logic read_enable1,input logic [9:0] read_x1,input logic [8:0] read_y1,
    output wire [7:0] read_depth1,output logic read_valid1,
    input logic write_enable1,input logic [9:0] write_x1,input logic [8:0] write_y1,
    input logic [7:0] write_depth1
);
    localparam WORDS=(FRAME_WIDTH/2)*FRAME_HEIGHT,AB=$clog2(WORDS);
    logic clear_active;
    logic [AB-1:0] clear_address;
    wire [1:0] re={read_enable1,read_enable},we={write_enable1,write_enable};
    wire [9:0] rx[0:1],wx[0:1];wire[8:0]ry[0:1],wy[0:1];wire[7:0]wz[0:1];
    assign rx[0]=read_x;assign rx[1]=read_x1;assign ry[0]=read_y;assign ry[1]=read_y1;
    assign wx[0]=write_x;assign wx[1]=write_x1;assign wy[0]=write_y;assign wy[1]=write_y1;
    assign wz[0]=write_depth;assign wz[1]=write_depth1;
    wire [1:0] valid;
    wire [7:0] result[0:1];
    assign read_depth=result[0];assign read_depth1=result[1];
    always_comb begin read_valid=valid[0];read_valid1=valid[1];clear_busy=clear_active;end
    always_ff @(posedge raster_clk or posedge reset)begin
        if(reset)begin clear_active<=0;clear_address<=0;end
        else if(!clear_active && clear_request)begin clear_active<=1;clear_address<=0;end
        else if(clear_active)begin
            if(clear_address==WORDS-1)begin clear_active<=0;clear_address<=0;end
            else clear_address<=clear_address+1'b1;
        end
    end
    generate for(genvar b=0;b<2;b++)begin:banks
        wire [AB-1:0] ra=ry[b]*(FRAME_WIDTH/2)+(rx[b]>>1);
        wire [AB-1:0] ram_write_address=clear_active?clear_address:wy[b]*(FRAME_WIDTH/2)+(wx[b]>>1);
        wire [7:0] ram_write_depth=clear_active?8'd0:wz[b];
        wire ram_write_enable=!reset && (clear_active || (we[b] && wx[b]<FRAME_WIDTH && wy[b]<FRAME_HEIGHT && wx[b][0]==b && !clear_request));
        wire ren=re[b] && rx[b]<FRAME_WIDTH && ry[b]<FRAME_HEIGHT && rx[b][0]==b && !clear_active && !clear_request && !reset;
        wire [7:0] q;
        logic forwarding,rv;
        logic [7:0] forwarded_depth;
        pixel_bank_ram #(.WORDS(WORDS)) memory(.write_clk(raster_clk),.read_clk(raster_clk),
            .write_address(ram_write_address),.write_data(ram_write_depth),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(ren),.read_data(q));
        assign valid[b]=rv;assign result[b]=forwarding?forwarded_depth:q;
        always_ff @(posedge raster_clk or posedge reset)begin
            if(reset)begin rv<=0;forwarding<=0;forwarded_depth<=0;end
            else begin
                rv<=ren;forwarding<=ren && ram_write_enable && ra==ram_write_address;
                if(ren && ram_write_enable && ra==ram_write_address)forwarded_depth<=ram_write_depth;
            end
        end
    end endgenerate
endmodule
'''

COLOR_BANKS = '''// Raster writes both parity banks; VGA reads one bank with registered parity.
module framebuffer_banked #(parameter int FRAME_WIDTH=320,FRAME_HEIGHT=240)(
    input logic reset,raster_clk,raster_write,input logic[9:0]raster_x,input logic[8:0]raster_y,
    input logic[7:0]raster_color,
    input logic raster_write1,input logic[9:0]raster_x1,input logic[8:0]raster_y1,input logic[7:0]raster_color1,
    input logic clear_request,output logic clear_busy,
    input logic display_clk,display_read_enable,input logic[9:0]display_x,input logic[8:0]display_y,
    output logic[7:0]display_pixel,output logic display_pixel_valid
);
    localparam WORDS=(FRAME_WIDTH/2)*FRAME_HEIGHT,AB=$clog2(WORDS);
    logic clear_active,parity;
    logic[AB-1:0]clear_address;
    wire[1:0]we={raster_write1,raster_write};
    wire[9:0]wx[0:1];wire[8:0]wy[0:1];wire[7:0]wc[0:1],q[0:1];
    assign wx[0]=raster_x;assign wx[1]=raster_x1;assign wy[0]=raster_y;assign wy[1]=raster_y1;
    assign wc[0]=raster_color;assign wc[1]=raster_color1;
    wire bounds=display_x<FRAME_WIDTH && display_y<FRAME_HEIGHT;
    wire[AB-1:0]ra=display_y*(FRAME_WIDTH/2)+(display_x>>1);
    assign clear_busy=clear_active;
    always_comb display_pixel=display_pixel_valid?q[parity]:8'd0;
    always_ff @(posedge display_clk or posedge reset)begin
        if(reset)begin parity<=0;display_pixel_valid<=0;end
        else begin parity<=display_x[0];display_pixel_valid<=display_read_enable && bounds;end
    end
    always_ff @(posedge raster_clk or posedge reset)begin
        if(reset)begin clear_active<=0;clear_address<=0;end
        else if(!clear_active && clear_request)begin clear_active<=1;clear_address<=0;end
        else if(clear_active)begin
            if(clear_address==WORDS-1)begin clear_active<=0;clear_address<=0;end
            else clear_address<=clear_address+1'b1;
        end
    end
    generate for(genvar b=0;b<2;b++)begin:banks
        wire[AB-1:0]ram_write_address=clear_active?clear_address:wy[b]*(FRAME_WIDTH/2)+(wx[b]>>1);
        wire[7:0]ram_write_data=clear_active?8'd0:wc[b];
        wire ram_write_enable=!reset && (clear_active || (we[b] && wx[b]<FRAME_WIDTH && wy[b]<FRAME_HEIGHT && wx[b][0]==b && !clear_request));
        pixel_bank_ram #(.WORDS(WORDS)) memory(.write_clk(raster_clk),.read_clk(display_clk),
            .write_address(ram_write_address),.write_data(ram_write_data),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(display_read_enable && bounds && display_x[0]==b),.read_data(q[b]));
    end endgenerate
endmodule
'''
