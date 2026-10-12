"""Retain Q4 screen coordinates and reciprocal fractions for depth-plane setup."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def generate(replace_once,write):
    dest=ROOT/'rtl/generated'
    p=dest/'renderer_types.svh';s=p.read_text()
    s=s.replace('    logic [7:0] color;','''`ifdef SOC_SUBPIXEL_DEPTH
    logic [3:0] xf0,xf1,xf2,yf0,yf1,yf2,zf0,zf1,zf2;
`endif
    logic [7:0] color;''',1);write(p,s)
    p=dest/'transform_3d_pipeline.sv';s=p.read_text()
    anchor='    logic signed [33:0] fan_area;'
    extra='''`ifdef SOC_SUBPIXEL_DEPTH
    logic [3:0] polygon_xf[0:MAX_VERTICES-1],polygon_yf[0:MAX_VERTICES-1],polygon_zf[0:MAX_VERTICES-1];
    logic [3:0] clipped_xf[0:MAX_VERTICES-1],clipped_yf[0:MAX_VERTICES-1],clipped_zf[0:MAX_VERTICES-1];
    logic [3:0] project_zf;
    logic signed [17:0] intersect_fp_x,intersect_fp_y,intersect_fp_z;
    function automatic logic signed [17:0] interpolate_fp(input logic signed [17:0] a,b,input logic[16:0] t);
        logic signed [18:0] delta;logic signed [17:0] fraction;
        logic signed [36:0] product;logic signed [37:0] result;
        begin delta=$signed(b)-$signed(a);fraction=$signed({1'b0,t});product=delta*fraction;
            result=$signed(a)+(product>>>16);interpolate_fp=result[17:0];end
    endfunction
`endif
'''
    s=replace_once(s,anchor,extra+anchor)
    anchor='        if (clip_is_near) begin\n            intersection_z = projection.near_z;'
    extra='''`ifdef SOC_SUBPIXEL_DEPTH
        intersect_fp_x=interpolate_fp($signed(edge_start_x)*18'sd16+$signed({1'b0,polygon_xf[edge_start_index]}),
            $signed(edge_end_x)*18'sd16+$signed({1'b0,polygon_xf[clip_edge_index]}),divider_quotient[16:0]);
        intersect_fp_y=interpolate_fp($signed(edge_start_y)*18'sd16-$signed({1'b0,polygon_yf[edge_start_index]}),
            $signed(edge_end_y)*18'sd16-$signed({1'b0,polygon_yf[clip_edge_index]}),divider_quotient[16:0]);
        intersect_fp_z=interpolate_fp($signed(edge_start_z)*18'sd16+$signed({1'b0,polygon_zf[edge_start_index]}),
            $signed(edge_end_z)*18'sd16+$signed({1'b0,polygon_zf[clip_edge_index]}),divider_quotient[16:0]);
        if(!clip_is_near) begin
            case(screen_plane)
                0:intersect_fp_x=0;1:intersect_fp_x=$signed(RIGHT_EDGE)*18'sd16;
                2:intersect_fp_y=0;3:intersect_fp_y=$signed(BOTTOM_EDGE)*18'sd16;
            endcase
            intersection_x=intersect_fp_x>>>4;intersection_y=(intersect_fp_y+18'sd15)>>>4;
            intersection_z=intersect_fp_z>>>4;
        end
`endif
'''
    s=replace_once(s,anchor,extra+anchor)
    for context in ('clipped_count','clip_copy_index'):
        if context=='clipped_count':
            anchor='                        clipped_z[clipped_count] <= edge_end_z;'
            extra='''
`ifdef SOC_SUBPIXEL_DEPTH
                        clipped_xf[clipped_count]<=polygon_xf[clip_edge_index];
                        clipped_yf[clipped_count]<=polygon_yf[clip_edge_index];
                        clipped_zf[clipped_count]<=polygon_zf[clip_edge_index];
`endif'''
            if s.count(anchor)!=1:raise RuntimeError('Clip endpoint anchor')
            s=s.replace(anchor,anchor+extra)
            anchor='                    clipped_z[clipped_count] <= edge_end_z;'
            s=replace_once(s,'\n'+anchor,'\n'+anchor+extra)
        else:
            anchor='                        polygon_z[clip_copy_index] <= clipped_z[clip_copy_index];'
            s=replace_once(s,anchor,anchor+'''
`ifdef SOC_SUBPIXEL_DEPTH
                        polygon_xf[clip_copy_index]<=clipped_xf[clip_copy_index];
                        polygon_yf[clip_copy_index]<=clipped_yf[clip_copy_index];
                        polygon_zf[clip_copy_index]<=clipped_zf[clip_copy_index];
`endif''')
    anchor='                        clipped_z[clipped_count] <= intersection_z;'
    s=replace_once(s,anchor,anchor+'''
`ifdef SOC_SUBPIXEL_DEPTH
                        clipped_xf[clipped_count]<=intersect_fp_x[3:0];
                        clipped_yf[clipped_count]<=-intersect_fp_y[3:0];
                        clipped_zf[clipped_count]<=intersect_fp_z[3:0];
`endif''')
    anchor='                        project_product_x <= '
    s=replace_once(s,anchor,'''`ifdef SOC_SUBPIXEL_DEPTH
                        project_zf<=divider_quotient[3:0];
`endif
'''+anchor)
    anchor='                    polygon_z[project_index] <= project_depth;'
    s=replace_once(s,anchor,anchor+'''
`ifdef SOC_SUBPIXEL_DEPTH
                    polygon_xf[project_index]<=project_scaled_x[23:20];
                    polygon_yf[project_index]<=project_scaled_y[23:20];
                    polygon_zf[project_index]<=project_zf;
`endif''')
    anchor='                        out_data.color <= active_triangle.color;'
    extra='`ifdef SOC_SUBPIXEL_DEPTH\n'
    for vertex,index in ((0,'0'),(1,'fan_index'),(2,"fan_index + 1'b1")):
        for axis in ('x','y','z'):extra+=f'                        out_data.{axis}f{vertex}<=polygon_{axis}f[{index}];\n'
    s=replace_once(s,anchor,extra+'`endif\n'+anchor);write(p,s)
    p=dest/'triangle_setup_engine.sv';s=p.read_text()
    declarations='''`ifdef SOC_SUBPIXEL_DEPTH
    localparam DEPTH_NUM_BITS=40,DEPTH_DEN_BITS=32;
    logic [3:0] xf[0:2],yf[0:2],zf[0:2];
    wire signed [14:0] fx0=$signed({1'b0,v0_x,4'b0})+$signed({1'b0,xf[0]});
    wire signed [14:0] fx1=$signed({1'b0,v1_x,4'b0})+$signed({1'b0,xf[1]});
    wire signed [14:0] fx2=$signed({1'b0,v2_x,4'b0})+$signed({1'b0,xf[2]});
    wire signed [14:0] fy0=$signed({1'b0,v0_y,4'b0})-$signed({1'b0,yf[0]});
    wire signed [14:0] fy1=$signed({1'b0,v1_y,4'b0})-$signed({1'b0,yf[1]});
    wire signed [14:0] fy2=$signed({1'b0,v2_y,4'b0})-$signed({1'b0,yf[2]});
    wire signed [31:0] fp_area=(fx1-fx0)*(fy2-fy0)-(fx2-fx0)*(fy1-fy0);
    wire signed [14:0] fp_offset_x=$signed({1'b0,clipped_min_x,4'b0})-fx0;
    wire signed [14:0] fp_offset_y=$signed({1'b0,clipped_min_y,4'b0})-fy0;
`else
    localparam DEPTH_NUM_BITS=32,DEPTH_DEN_BITS=22;
`endif
'''
    s=replace_once(s,'    logic signed [31:0] depth_dx_numerator;',declarations+'    logic signed [DEPTH_NUM_BITS-1:0] depth_dx_numerator;')
    for n in ('depth_dy_numerator','depth_dx_quotient','depth_dy_quotient'):
        s=replace_once(s,'logic signed [31:0] '+n+';','logic signed [DEPTH_NUM_BITS-1:0] '+n+';')
    s=replace_once(s,'    logic signed [31:0] depth_step_y;','    logic signed [31:0] depth_step_y;\n`ifdef SOC_SUBPIXEL_DEPTH\n    wire signed [47:0] fp_start_x=depth_step_x*fp_offset_x,fp_start_y=depth_step_y*fp_offset_y;\n`endif')
    s=s.replace('.NUMERATOR_WIDTH(32),\n        .DENOMINATOR_WIDTH(22)', '.NUMERATOR_WIDTH(DEPTH_NUM_BITS),\n        .DENOMINATOR_WIDTH(DEPTH_DEN_BITS)')
    s=s.replace('.denominator(standard_area)', '''.denominator(
`ifdef SOC_SUBPIXEL_DEPTH
            fp_area
`else
            standard_area
`endif
        )''')
    anchor='        depth_dx_numerator = (depth_f1 - depth_f0) * depth_dy2 -\n                             (depth_f2 - depth_f0) * depth_dy1;\n        depth_dy_numerator = depth_dx1 * (depth_f2 - depth_f0) -\n                             depth_dx2 * (depth_f1 - depth_f0);'
    s=replace_once(s,anchor,'''`ifdef SOC_SUBPIXEL_DEPTH
        depth_f0=depth_f0+$signed({1'b0,zf[0],4'b0});
        depth_f1=depth_f1+$signed({1'b0,zf[1],4'b0});
        depth_f2=depth_f2+$signed({1'b0,zf[2],4'b0});
        depth_dx_numerator=(((depth_f1-depth_f0)*(fy2-fy0))-((depth_f2-depth_f0)*(fy1-fy0)))<<<4;
        depth_dy_numerator=(((fx1-fx0)*(depth_f2-depth_f0))-((fx2-fx0)*(depth_f1-depth_f0)))<<<4;
`else
'''+anchor+'\n`endif')
    for vertex in range(3):
        anchor=f'                        v{vertex}_depth <= triangle_data.z{vertex};'
        extra='\n`ifdef SOC_SUBPIXEL_DEPTH\n'+''.join(f'                        {axis}f[{vertex}]<=triangle_data.{axis}f{vertex};\n' for axis in ('x','y','z'))+'`endif'
        s=replace_once(s,anchor,anchor+extra)
    s=replace_once(s,"setup_base_depth <= $signed({1'b0, v0_depth, 8'b0});",'setup_base_depth <= depth_f0;')
    anchor='                    depth_start_x <= depth_step_x * setup_offset_x;\n                    depth_start_y <= depth_step_y * setup_offset_y;'
    s=replace_once(s,anchor,'''`ifdef SOC_SUBPIXEL_DEPTH
                    depth_start_x<=fp_start_x>>>4;depth_start_y<=fp_start_y>>>4;
`else
'''+anchor+'\n`endif');write(p,s)
