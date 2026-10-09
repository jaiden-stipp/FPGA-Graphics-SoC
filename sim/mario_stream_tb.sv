`timescale 1ns/1ps
`include "renderer_types.svh"
`include "game_stats.svh"
`include "mario-test_symbols.svh"
module mario_stream_tb;
    logic clk=0, reset=1;
    always #10 clk=~clk;
    logic [31:0] pc, addr, wdata, rdata, instruction, scratch;
    logic [2:0] funct3;
    logic read_en,write_en,misaligned,write_performed;
    logic [7:0] byte_data,buttons=0;
    logic byte_valid,byte_ready,decoder_error,frame_pending;
    logic [3:0] error_flags;
    logic command_valid,command_ready=1,frame_done=0;
    logic [31:0] frame_done_id=0;
    graphics_command_t command_data;
    model_matrix_3x4_t matrix,first_model,frame_model;
    model_matrix_3x4_t view,first_view;
    integer first_camera_y,actor_camera_y;
    integer frames=0,draws=0,defines=0,triangles=0,cycles=0;
    bit moved=0,jumped=0,landed=0,jumped_again=0;
    logic [3:0] animation_seen=0;
    integer actor_updates=0,animation_changes=0;
    logic [47:0] actor_vertices[0:15][0:127];
    logic [47:0] vertex_value;
    integer vertex_handle,vertex_index;
    RV32I_SoC cpu (
        .clk(clk),.rst(reset),.debug_pc(pc),.soc_instruction(instruction),
        .soc_rdata(rdata),.soc_misaligned(misaligned),.soc_write_performed(write_performed),
        .soc_pc(),.soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),
        .soc_read_en(read_en),.soc_write_en(write_en),
        .trace_valid(),.trace_pc(),.trace_instruction(),.trace_reg_write(),.trace_rd(),
        .trace_rd_data(),.trace_mem_read(),.trace_mem_write(),.trace_mem_address(),
        .trace_mem_data(),.trace_mem_funct3(),.trace_branch(),.trace_jump(),.trace_jalr(),.commit_valid()
    );
    soc_memory #(.HEX_FILE("build/mario-test.hex")) memory (
        .clk(clk),.reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(funct3),
        .read_en(read_en),.write_en(write_en),.instruction(instruction),.rdata(rdata),
        .misaligned(misaligned),.write_performed(write_performed),
        .byte_data(byte_data),.byte_valid(byte_valid),.byte_ready(byte_ready),
        .decoder_error(decoder_error),.command_error(1'b0),
        .frame_done(frame_done),.frame_done_id(frame_done_id),.frame_statistics(416'b0),
        .buttons(buttons),.frame_pending(frame_pending),.error_flags(error_flags),.scratch(scratch)
    );
    graphics_command_stream_decoder decoder (
        .clk(~clk),.reset(reset),.byte_data(byte_data),.byte_valid(byte_valid),.byte_ready(byte_ready),
        .command_data(command_data),.command_valid(command_valid),.command_ready(command_ready),.decoder_error(decoder_error)
    );
    always @(negedge clk) if (!reset) begin
        cycles<=cycles+1; frame_done<=0; command_ready<=(cycles%11)<7;
        if (command_valid && command_ready) case (command_data.opcode)
            GFX_CMD_SET_PALETTE,GFX_CMD_SET_PROJECTION: begin
                if (frames!=0) $fatal(1,"Game reuploads geometry during rendering");
            end
            GFX_CMD_UPLOAD_VERTEX: begin
                vertex_handle=`GFX_MESH_HANDLE(command_data);vertex_index=`GFX_MESH_ELEMENT(command_data);
                vertex_value=command_data.payload[47:0];
                if (frames && vertex_handle<`MARIO_WORLD_MESHES) $fatal(1,"Terrain vertices changed");
                if (vertex_handle>=`MARIO_WORLD_MESHES) begin
                    if (frames) begin
                        actor_updates=actor_updates+1;
                        if (actor_vertices[vertex_handle][vertex_index]!=vertex_value) animation_changes=animation_changes+1;
                    end
                    actor_vertices[vertex_handle][vertex_index]=vertex_value;
                end
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
            GFX_CMD_SET_VIEW_MATRIX: view=`GFX_VIEW_MATRIX(command_data);
            GFX_CMD_BEGIN_FRAME: begin
                if (`GFX_ARGUMENT(command_data)!=frames+1) $fatal(1,"Frame sequence");
                frames<=frames+1; draws<=0;
`ifdef MARIO_ANIMATED
                if (frames && actor_updates!=`MARIO_ACTOR_VERTICES) $fatal(1,"Incomplete animated vertex update");
                animation_seen[memory.ram.mem[`MARIO_TEST_CLIP_ADDR>>2]]=1;
                actor_updates=0;
`endif
            end
            GFX_CMD_DRAW_MESH: begin
                if (`GFX_DRAW_MESH_HANDLE(command_data)!=draws) $fatal(1,"Mesh order");
                matrix=`GFX_MODEL_MATRIX(command_data);
                if (draws<`MARIO_WORLD_MESHES) begin
                    if (matrix!=192'h010000000000000000000100000000000000000001000000)
                        $fatal(1,"Terrain model changed");
                end else if (draws==`MARIO_WORLD_MESHES) begin
                    frame_model=matrix;
                    actor_camera_y=(($signed(view.m11)*$signed(matrix.m13)+
                                     $signed(view.m12)*$signed(matrix.m23))>>>8)+$signed(view.m13);
                    if (frames==1) begin
                        first_model=matrix; first_view=view; first_camera_y=actor_camera_y;
                    end
                    if (frames==2) begin
                        if (matrix.m03>=first_model.m03 || matrix.m02==0) $fatal(1,"Move/facing ignored");
                        moved=1;
                    end
                    if (frames==3) begin
                        if (matrix.m13<=first_model.m13) $fatal(1,"Jump ignored");
                        if (actor_camera_y<=first_camera_y+4) $fatal(1,"Camera locks jump to screen");
                        jumped=1;
                    end
                    if (frames==30) begin
                        if (matrix.m13>first_model.m13+4) $fatal(1,"Landing or held jump failed");
                        landed=1;
                    end
                    if (frames==32) begin
                        if (matrix.m13<=first_model.m13+4) $fatal(1,"Released jump did not retrigger");
                        jumped_again=1;
                    end
                    if (frames==33 && (matrix!=first_model || view!=first_view))
                        $fatal(1,"Respawn pose/camera failed");
                end else if (matrix!=frame_model) $fatal(1,"Actor chunks have different transforms");
                draws<=draws+1;
            end
            GFX_CMD_END_FRAME: begin
                if (draws!=`MARIO_EXPECTED_MESHES) $fatal(1,"Incomplete game frame");
                frame_done_id<=frames; frame_done<=1;
                if (frames==1) buttons<=1;
                if (frames==2) buttons<=16;
                if (frames==30) buttons<=0;
                if (frames==31) buttons<=16;
                if (frames==32) buttons<=15;
            end
            default: $fatal(1,"Unexpected game opcode");
        endcase
    end
    initial begin
        repeat (5) @(posedge clk); #1; reset=0;
        for (integer i=0; i<40000000; i=i+1) begin
            @(posedge clk); #1;
            if (error_flags || scratch==32'hdead0001) $fatal(1,"Game CPU failure PC=%h",pc);
            if (scratch==33) begin
                if (triangles!=`MARIO_EXPECTED_TRIANGLES || defines!=`MARIO_EXPECTED_MESHES ||
                    frame_pending || !moved || !jumped || !landed || !jumped_again) $fatal(1,"Game lifecycle");
`ifdef MARIO_ANIMATED
                if (animation_seen!=4'b1111 || animation_changes<100) $fatal(1,"Animation lifecycle/pose updates failed");
`endif
                $display("PASS mario_stream_tb (RV32I movement, facing, jumping, landing, held-key and respawn; %0d cycles)",i);
                $finish;
            end
        end
        $fatal(1,"Game CPU timeout PC=%h frame=%h",pc,scratch);
    end
endmodule
