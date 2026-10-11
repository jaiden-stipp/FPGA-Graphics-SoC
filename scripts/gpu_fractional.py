"""Generated, backwards-compatible fractional model translation extension."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def generate(replace_once,write):
 src=ROOT/'external/renderer/rtl';dest=ROOT/'rtl/generated'
 types=(src/'common/renderer_types.svh').read_text()
 types=replace_once(types,'logic [199:0] payload;','logic [223:0] payload;')
 types=replace_once(types,"GFX_CMD_SET_PROJECTION = 4'd10","GFX_CMD_SET_PROJECTION = 4'd10,\n    GFX_CMD_DRAW_MESH_Q8 = 4'd11")
 types=types.replace('`include "protocol_generated.svh"','`include "protocol_generated.svh"\n`define GFX_WIRE_CMD_DRAW_MESH_Q8 8\'d13')
 write(dest/'renderer_types.svh',types)
 decoder=(src/'command/graphics_command_stream_decoder.sv').read_text()
 decoder=replace_once(decoder,'                            `GFX_WIRE_CMD_SET_VIEW_MATRIX: begin', '''                            `GFX_WIRE_CMD_DRAW_MESH_Q8: begin
                                decoded_command.opcode <= GFX_CMD_DRAW_MESH_Q8;
                                if (byte_data == 8'd28) state <= PAYLOAD;
                                else begin decoder_error <= 1'b1; state <= SYNC_G; end
                            end
                            `GFX_WIRE_CMD_SET_VIEW_MATRIX: begin''')
 decoder=replace_once(decoder,'                            `GFX_WIRE_CMD_DRAW_MESH: decoded_command.payload[', '''                            `GFX_WIRE_CMD_DRAW_MESH_Q8: begin
                                if (payload_index < 25)
                                    decoded_command.payload[199-payload_index*8-:8] <= byte_data;
                                else decoded_command.payload[223-(payload_index-25)*8-:8] <= byte_data;
                            end
                            `GFX_WIRE_CMD_DRAW_MESH: decoded_command.payload[''')
 write(dest/'graphics_command_stream_decoder.sv',decoder)
 processor=(src/'command/graphics_command_processor.sv').read_text()
 processor=replace_once(processor,'    output model_matrix_3x4_t mesh_draw_matrix,','    output model_matrix_3x4_t mesh_draw_matrix,\n    output logic [23:0] mesh_draw_fraction,')
 processor=processor.replace('command_data.opcode == GFX_CMD_DRAW_MESH','(command_data.opcode == GFX_CMD_DRAW_MESH || command_data.opcode == GFX_CMD_DRAW_MESH_Q8)')
 processor=replace_once(processor,'        mesh_draw_matrix = `GFX_MODEL_MATRIX(command_data);','        mesh_draw_matrix = `GFX_MODEL_MATRIX(command_data);\n        mesh_draw_fraction = command_data.opcode == GFX_CMD_DRAW_MESH_Q8 ? command_data.payload[223:200] : 24\'b0;')
 processor=replace_once(processor,'GFX_CMD_DRAW_MESH: state <= MESH_WAIT;','GFX_CMD_DRAW_MESH, GFX_CMD_DRAW_MESH_Q8: state <= MESH_WAIT;')
 write(dest/'graphics_command_processor.sv',processor)
 mesh=(src/'pipeline/indexed_mesh_store.sv').read_text()
 mesh=replace_once(mesh,'    input model_matrix_3x4_t draw_matrix,','    input model_matrix_3x4_t draw_matrix,\n    input logic [23:0] draw_fraction,')
 mesh=replace_once(mesh,'    model_matrix_3x4_t active_matrix;','    model_matrix_3x4_t active_matrix;\n    logic [23:0] active_fraction;')
 mesh=replace_once(mesh,'transformed_component = (product_sum >>> 8) + translation;',"transformed_component = ((product_sum + $signed({26'b0,active_fraction[23-transform_component_number*8-:8]})) >>> 8) + translation;")
 mesh=replace_once(mesh,"            active_matrix <= '0;","            active_matrix <= '0;\n            active_fraction <= '0;")
 mesh=replace_once(mesh,'                            active_matrix <= draw_matrix;','                            active_matrix <= draw_matrix;\n                            active_fraction <= draw_fraction;')
 # Register products before fractional rounding/translation. The first fit
 # measured a negative setup margin from component selection to output data.
 mesh=replace_once(mesh,'        TRANSFORM_COMPONENT,','        TRANSFORM_PRODUCT,\n        TRANSFORM_COMPONENT,')
 mesh=replace_once(mesh,'    logic signed [34:0] transformed_component;', '    logic signed [34:0] transformed_component;\n    logic signed [33:0] saved_sum;\n    logic signed [15:0] saved_translation;\n    logic [7:0] saved_fraction;')
 mesh=replace_once(mesh,"transformed_component = ((product_sum + $signed({26'b0,active_fraction[23-transform_component_number*8-:8]})) >>> 8) + translation;", "transformed_component = ((saved_sum + $signed({26'b0,saved_fraction})) >>> 8) + saved_translation;")
 mesh=replace_once(mesh,"            active_fraction <= '0;", "            active_fraction <= '0;\n            saved_sum <= '0; saved_translation <= '0; saved_fraction <= '0;")
 mesh=replace_once(mesh,'                    state <= TRANSFORM_COMPONENT;', '                    state <= TRANSFORM_PRODUCT;')
 mesh=replace_once(mesh,'                TRANSFORM_COMPONENT: begin', "                TRANSFORM_PRODUCT: begin\n                    saved_sum <= product_sum; saved_translation <= translation;\n                    saved_fraction <= active_fraction[23-transform_component_number*8-:8];\n                    state <= TRANSFORM_COMPONENT;\n                end\n                TRANSFORM_COMPONENT: begin\n                    state <= TRANSFORM_PRODUCT;")
 write(dest/'indexed_mesh_store.sv',mesh)
 core=(dest/'graphics_renderer_core.sv').read_text()
 core=replace_once(core,'    model_matrix_3x4_t mesh_draw_matrix;','    model_matrix_3x4_t mesh_draw_matrix;\n    logic [23:0] mesh_draw_fraction;')
 core=replace_once(core,'        .mesh_draw_matrix(mesh_draw_matrix),','        .mesh_draw_matrix(mesh_draw_matrix),\n        .mesh_draw_fraction(mesh_draw_fraction),')
 core=replace_once(core,'        .draw_matrix(mesh_draw_matrix),','        .draw_matrix(mesh_draw_matrix),\n        .draw_fraction(mesh_draw_fraction),')
 write(dest/'graphics_renderer_core.sv',core)
