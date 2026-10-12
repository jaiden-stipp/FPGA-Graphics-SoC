"""Selectable 12-bit reciprocal depth; external commands and palette stay intact."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def generate(replace_once,write):
    dest=ROOT/'rtl/generated'
    p=dest/'renderer_types.svh';s=p.read_text()
    s=replace_once(s,'`define RENDERER_TYPES_SVH','''`define RENDERER_TYPES_SVH
`ifdef SOC_DEPTH12
`define GFX_DEPTH_BITS 12
`else
`define GFX_DEPTH_BITS 8
`endif''')
    for n in ('z0','z1','z2'):s=replace_once(s,'logic [7:0] '+n+';','logic [`GFX_DEPTH_BITS-1:0] '+n+';')
    write(p,s)
    p=dest/'triangle_setup_types.svh';s=p.read_text()
    s=replace_once(s,'logic [7:0] color, minimum_depth, maximum_depth;','logic [7:0] color;\n    logic [`GFX_DEPTH_BITS-1:0] minimum_depth, maximum_depth;')
    write(p,s)
    names=('renderer.sv','renderer_serial.sv','triangle_setup_engine.sv','renderer_overlap.sv','renderer_dual.sv')
    for name in names:
        p=dest/name;s=p.read_text()
        s=re.sub(r'\[7:0\](\s+)(?=(?:v[012]_depth|minimum_depth|maximum_depth|current_depth_byte|lane1_depth_byte|depth_read_value|depth_write_value))',r'[`GFX_DEPTH_BITS-1:0]\1',s)
        s=s.replace('logic signed [16:0] depth_f','logic signed [`GFX_DEPTH_BITS+8:0] depth_f')
        s=s.replace('current_depth[15:8]','current_depth[`GFX_DEPTH_BITS+7:8]').replace('lane1_depth[15:8]','lane1_depth[`GFX_DEPTH_BITS+7:8]')
        write(p,s)
    p=dest/'graphics_pipeline.sv';s=p.read_text()
    s=replace_once(s,'logic [7:0] raster_color1,depth_read_value1,depth_write_value1;', 'logic [7:0] raster_color1;\n    logic [`GFX_DEPTH_BITS-1:0] depth_read_value1,depth_write_value1;')
    s=re.sub(r'\[7:0\](\s+)(?=depth_(?:read|write)_value)',r'[`GFX_DEPTH_BITS-1:0]\1',s)
    write(p,s)
    s=(ROOT/'external/renderer/rtl/pipeline/depth_test_stage.sv').read_text()
    s='`include "renderer_types.svh"\n'+s
    s=re.sub(r'\[7:0\](\s+)(?=(?:candidate_depth|pending_depth|depth_read_value|depth_write_value))',r'[`GFX_DEPTH_BITS-1:0]\1',s)
    write(dest/'depth_test_stage.sv',s)
    p=dest/'transform_3d_pipeline.sv';s=p.read_text()
    s=replace_once(s,'project_depth <= divider_quotient[23:8];','''`ifdef SOC_DEPTH12
                        project_depth <= divider_quotient > 32'sd65520 ? 16'd4095 : (divider_quotient >> 4);
`else
                        project_depth <= divider_quotient[23:8];
`endif''')
    s=re.sub(r'(out_data\.z[012] <= polygon_z\[[^;]+?\])\[7:0\];',r'\1[`GFX_DEPTH_BITS-1:0];',s)
    write(p,s)
    p=dest/'pixel_bank_ram.sv';s=p.read_text()
    s=s.replace('ADDR_BITS=$clog2(WORDS))','ADDR_BITS=$clog2(WORDS), DATA_BITS=8)')
    s=s.replace('[7:0]','[DATA_BITS-1:0]').replace('.width_a(8),.width_b(8)','.width_a(DATA_BITS),.width_b(DATA_BITS)')
    write(p,s)
    p=dest/'zbuffer_banked.sv';s=p.read_text()
    s='`include "renderer_types.svh"\n'+s
    s=s.replace('[7:0]','[`GFX_DEPTH_BITS-1:0]').replace('clear_active?8\'d0:wz[b]',"clear_active?`GFX_DEPTH_BITS'd0:wz[b]")
    anchor='''        pixel_bank_ram #(.WORDS(WORDS)) memory(.write_clk(raster_clk),.read_clk(raster_clk),
            .write_address(ram_write_address),.write_data(ram_write_depth),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(ren),.read_data(q));'''
    replacement='''`ifdef SOC_DEPTH12
        // Nine-bit M9K words retain byte-bank capacity. Three independent
        // one-bit planes hold the upper bits without 18-bit word padding.
        pixel_bank_ram #(.WORDS(WORDS),.DATA_BITS(9)) memory(.write_clk(raster_clk),.read_clk(raster_clk),
            .write_address(ram_write_address),.write_data(ram_write_depth[8:0]),.write_enable(ram_write_enable),
            .read_address(ra),.read_enable(ren),.read_data(q[8:0]));
        genvar bitplane;
        for(bitplane=9;bitplane<12;bitplane=bitplane+1)begin:extra_depth
            pixel_bank_ram #(.WORDS(WORDS),.DATA_BITS(1)) memory(.write_clk(raster_clk),.read_clk(raster_clk),
                .write_address(ram_write_address),.write_data(ram_write_depth[bitplane]),.write_enable(ram_write_enable),
                .read_address(ra),.read_enable(ren),.read_data(q[bitplane]));
        end
`else
'''+anchor+'\n`endif'
    s=replace_once(s,anchor,replacement);write(p,s)
