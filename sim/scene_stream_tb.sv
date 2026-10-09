`timescale 1ns/1ps
`include "renderer_types.svh"
`include "scene_stats.svh"
module scene_stream_tb;
    logic clk=0, reset=1;
    always #10 clk=~clk;
    logic [31:0] pc, addr, wdata, rdata, instruction, scratch;
    logic [2:0] funct3;
    logic read_en, write_en, misaligned, write_performed;
    logic [7:0] byte_data, buttons=0;
    logic byte_valid, byte_ready, decoder_error, frame_pending;
    logic [3:0] error_flags;
    logic command_valid, command_ready=1, frame_done=0;
    logic [31:0] frame_done_id=0;
    graphics_command_t command_data;
    model_matrix_3x4_t matrix;
    integer frames=0, draws=0, defines=0, triangles=0, views=0, cycles=0;
    logic [191:0] initial_view;
    RV32I_SoC cpu (
        .clk(clk), .rst(reset), .debug_pc(pc), .soc_instruction(instruction),
        .soc_rdata(rdata), .soc_misaligned(misaligned), .soc_write_performed(write_performed),
        .soc_pc(), .soc_addr(addr), .soc_wdata(wdata), .soc_funct3(funct3),
        .soc_read_en(read_en), .soc_write_en(write_en),
        .trace_valid(), .trace_pc(), .trace_instruction(), .trace_reg_write(), .trace_rd(),
        .trace_rd_data(), .trace_mem_read(), .trace_mem_write(), .trace_mem_address(),
        .trace_mem_data(), .trace_mem_funct3(), .trace_branch(), .trace_jump(), .trace_jalr(), .commit_valid()
    );
    soc_memory #(.HEX_FILE("build/scene-test.hex")) memory (
        .clk(clk), .reset(reset), .pc(pc), .addr(addr), .wdata(wdata), .funct3(funct3),
        .read_en(read_en), .write_en(write_en), .instruction(instruction), .rdata(rdata),
        .misaligned(misaligned), .write_performed(write_performed),
        .byte_data(byte_data), .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(1'b0),
        .frame_done(frame_done), .frame_done_id(frame_done_id), .frame_statistics(416'b0),
        .buttons(buttons), .frame_pending(frame_pending), .error_flags(error_flags), .scratch(scratch)
    );
    graphics_command_stream_decoder decoder (
        .clk(~clk), .reset(reset), .byte_data(byte_data), .byte_valid(byte_valid), .byte_ready(byte_ready),
        .command_data(command_data), .command_valid(command_valid), .command_ready(command_ready), .decoder_error(decoder_error)
    );
    always @(negedge clk) if (!reset) begin
        cycles<=cycles+1; frame_done<=0; command_ready<=(cycles%11)<7;
        if (command_valid && command_ready) case (command_data.opcode)
            GFX_CMD_SET_PALETTE, GFX_CMD_SET_PROJECTION, GFX_CMD_UPLOAD_VERTEX: begin
                if (frames!=0) $fatal(1,"Scene reuploaded during rendering");
            end
            GFX_CMD_DEFINE_MESH: begin
                if (frames!=0 || `GFX_MESH_VERTEX_COUNT(command_data)>128 ||
                    `GFX_MESH_TRIANGLE_COUNT(command_data)>256) $fatal(1,"Mesh capacity");
                defines<=defines+1;
            end
            GFX_CMD_UPLOAD_INDEX: begin
                if (frames!=0) $fatal(1,"Indices reuploaded");
                triangles<=triangles+1;
            end
            GFX_CMD_SET_VIEW_MATRIX: begin
                matrix=`GFX_VIEW_MATRIX(command_data);
                if (views==0) initial_view=command_data.payload[191:0];
                if (views==1 && (matrix.m02==0 || matrix.m23!=3072)) $fatal(1,"Orbit input ignored");
                if (views==2 && (matrix.m02==0 || matrix.m23!=3008)) $fatal(1,"Zoom input ignored");
                if (views==3 && command_data.payload[191:0]!=initial_view) $fatal(1,"Reset input ignored");
                views<=views+1;
            end
            GFX_CMD_BEGIN_FRAME: begin
                if (`GFX_ARGUMENT(command_data)!=frames+1 || views!=frames+1) $fatal(1,"Frame/view sequence");
                frames<=frames+1; draws<=0;
            end
            GFX_CMD_DRAW_MESH: begin
                if (`GFX_DRAW_MESH_HANDLE(command_data)!=draws ||
                    `GFX_MODEL_MATRIX(command_data)!=192'h010000000000000000000100000000000000000001000000)
                    $fatal(1,"GPU model transform/mesh order");
                draws<=draws+1;
            end
            GFX_CMD_END_FRAME: begin
                if (draws!=`SCENE_EXPECTED_MESHES) $fatal(1,"Incomplete scene frame");
                frame_done_id<=frames; frame_done<=1;
                if (frames==1) buttons<=2;
                if (frames==2) buttons<=4;
                if (frames==3) buttons<=16;
                if (frames==4) buttons<=0;
            end
            default: $fatal(1,"Unexpected scene opcode");
        endcase
    end
    initial begin
        repeat (5) @(posedge clk); #1; reset=0;
        for (integer i=0; i<1500000; i=i+1) begin
            @(posedge clk); #1;
            if (error_flags || scratch==32'hdead0001) $fatal(1,"Scene CPU failure PC=%h",pc);
            if (scratch==4) begin
                if (triangles!=`SCENE_EXPECTED_TRIANGLES || defines!=`SCENE_EXPECTED_MESHES || frame_pending)
                    $fatal(1,"Scene lifecycle");
                $display("PASS scene_stream_tb (one-time SM64 upload, orbit/zoom/reset, %0d cycles)",i); $finish;
            end
        end
        $fatal(1,"Scene CPU timeout PC=%h",pc);
    end
endmodule
