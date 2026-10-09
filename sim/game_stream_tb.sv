`timescale 1ns/1ps
`include "renderer_types.svh"
// Real CPU runs game.c. Synthetic display completion keeps 56 ticks inexpensive.
module game_stream_tb;
    logic clk = 0, reset = 1;
    always #10 clk = ~clk;
    logic [31:0] pc, addr, wdata, rdata, instruction, scratch;
    logic [2:0] funct3;
    logic read_en, write_en, misaligned, write_performed;
    logic [7:0] byte_data;
    logic byte_valid, byte_ready, decoder_error, frame_pending;
    logic [3:0] error_flags;
    logic command_valid, command_ready = 1, frame_done = 0;
    logic [31:0] frame_done_id = 0;
    logic [7:0] buttons = 1;
    graphics_command_t command_data;
    model_matrix_3x4_t matrix;
    integer frames = 0, phase = 0, palettes = 0, defines = 0, vertices = 0, indices = 0;
    integer cycles = 0, expected_paddle;
    RV32I_SoC cpu (
        .clk(clk), .rst(reset), .debug_pc(pc), .soc_instruction(instruction),
        .soc_rdata(rdata), .soc_misaligned(misaligned),
        .soc_write_performed(write_performed), .soc_pc(), .soc_addr(addr),
        .soc_wdata(wdata), .soc_funct3(funct3), .soc_read_en(read_en),
        .soc_write_en(write_en), .trace_valid(), .trace_pc(), .trace_instruction(),
        .trace_reg_write(), .trace_rd(), .trace_rd_data(), .trace_mem_read(),
        .trace_mem_write(), .trace_mem_address(), .trace_mem_data(),
        .trace_mem_funct3(), .trace_branch(), .trace_jump(), .trace_jalr(), .commit_valid()
    );
    soc_memory #(.HEX_FILE("build/game-test.hex")) memory (
        .clk(clk), .reset(reset), .pc(pc), .addr(addr), .wdata(wdata),
        .funct3(funct3), .read_en(read_en), .write_en(write_en),
        .instruction(instruction), .rdata(rdata), .misaligned(misaligned),
        .write_performed(write_performed), .byte_data(byte_data),
        .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(1'b0),
        .frame_done(frame_done), .frame_done_id(frame_done_id), .frame_statistics(416'b0),
        .buttons(buttons), .frame_pending(frame_pending), .error_flags(error_flags), .scratch(scratch)
    );
    graphics_command_stream_decoder decoder (
        .clk(~clk), .reset(reset), .byte_data(byte_data), .byte_valid(byte_valid),
        .byte_ready(byte_ready), .command_data(command_data),
        .command_valid(command_valid), .command_ready(command_ready), .decoder_error(decoder_error)
    );
    always @(negedge clk) begin
        if (!reset) begin
            cycles <= cycles + 1;
            frame_done <= 0;
            command_ready <= (cycles % 11) < 7;
            if (command_valid && command_ready) begin
                case (command_data.opcode)
                    GFX_CMD_SET_VIEW_MATRIX: begin
                        if (frames != 0) $fatal(1, "View changed mid-game");
                    end
                    GFX_CMD_SET_PALETTE: begin
                        palettes <= palettes + 1;
                        if (palettes == 2 && `GFX_ARGUMENT(command_data) != 32'h02ff2828)
                            $fatal(1, "Miss feedback color");
                        if (palettes == 3 && `GFX_ARGUMENT(command_data) != 32'h0228ff28)
                            $fatal(1, "Catch feedback color");
                    end
                    GFX_CMD_DEFINE_MESH: begin
                        defines <= defines + 1;
                        if (`GFX_MESH_VERTEX_COUNT(command_data) != 4 ||
                            `GFX_MESH_TRIANGLE_COUNT(command_data) != 2)
                            $fatal(1, "Rectangle definition");
                    end
                    GFX_CMD_UPLOAD_VERTEX: vertices <= vertices + 1;
                    GFX_CMD_UPLOAD_INDEX: indices <= indices + 1;
                    GFX_CMD_BEGIN_FRAME: begin
                        if (phase != 0 || `GFX_ARGUMENT(command_data) != frames + 1)
                            $fatal(1, "Frame sequence");
                        frames <= frames + 1; phase <= 1;
                    end
                    GFX_CMD_DRAW_MESH: begin
                        matrix = `GFX_MODEL_MATRIX(command_data);
                        if (matrix.m00 != 256 || matrix.m11 != 256 || matrix.m22 != 256 ||
                            matrix.m23 != 1024) $fatal(1, "Fixed point model transform");
                        if (phase == 1) begin
                            if (frames == 1) expected_paddle = -32;
                            else if (frames < 4) expected_paddle = 0;
                            else if (frames < 13) expected_paddle = -32 * (frames - 3);
                            else if (frames <= 28) expected_paddle = -320;
                            else if (frames <= 36) expected_paddle = -320 + 32 * (frames - 28);
                            else expected_paddle = -64;
                            if (`GFX_DRAW_MESH_HANDLE(command_data) != 0 ||
                                matrix.m03 != expected_paddle || matrix.m13 != -240)
                                $fatal(1, "CPU input/movement frame=%0d x=%0d", frames, matrix.m03);
                            phase <= 2;
                        end else if (phase == 2) begin
                            if (`GFX_DRAW_MESH_HANDLE(command_data) != 1 ||
                                matrix.m03 != (frames < 28 ? -160 : (frames < 56 ? -80 : 0)) ||
                                matrix.m13 != (frames < 28 ? 240 - 16 * frames :
                                    (frames < 56 ? 240 - 16 * (frames - 28) : 240)))
                                $fatal(1, "CPU falling block/reset frame=%0d", frames);
                            phase <= 3;
                        end else $fatal(1, "Draw outside frame");
                    end
                    GFX_CMD_END_FRAME: begin
                        if (phase != 3) $fatal(1, "Incomplete frame");
                        phase <= 0; frame_done_id <= frames; frame_done <= 1;
                        // Change inputs before firmware samples the next tick.
                        if (frames == 1) buttons <= 2;
                        else if (frames == 2) buttons <= 3;
                        else if (frames < 28) buttons <= 1;
                        else if (frames < 36) buttons <= 2;
                        else buttons <= 3;
                    end
                    default: $fatal(1, "Unexpected game command");
                endcase
            end
        end
    end
    initial begin
        repeat (5) @(posedge clk); #1; reset = 0;
        for (integer i = 0; i < 1000000; i = i + 1) begin
            @(posedge clk); #1;
            if (error_flags != 0 || scratch == 32'hdead0001) $fatal(1, "Game failed PC=%h", pc);
            if (scratch == 56) begin
                if (frames != 56 || phase != 0 || frame_pending || palettes != 4 ||
                    defines != 2 || vertices != 8 || indices != 4) $fatal(1, "Game lifecycle");
                $display("PASS game_stream_tb (56 CPU game ticks, input/catch/miss/mesh reuse)");
                $finish;
            end
        end
        $fatal(1, "Game timeout PC=%h", pc);
    end
endmodule
