`timescale 1ns/1ps
`include "renderer_types.svh"
// Real CPU + firmware + RAM + MMIO + upstream decoder; synthetic frame completion.
module cpu_stream_tb;
    logic clk = 0, reset = 1;
    always #10 clk = ~clk;
    logic [31:0] pc, addr, wdata, rdata, instruction, scratch;
    logic [2:0] funct3;
    logic read_en, write_en, misaligned, write_performed;
    logic [7:0] byte_data;
    logic byte_valid, byte_ready, decoder_error, frame_pending;
    logic [3:0] error_flags;
    logic command_valid, command_ready = 1, frame_done = 0;
    graphics_command_t command_data;
    integer commands = 0, cycles = 0;
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
    soc_memory #(.HEX_FILE("build/triangle.hex")) memory (
        .clk(clk), .reset(reset), .pc(pc), .addr(addr), .wdata(wdata),
        .funct3(funct3), .read_en(read_en), .write_en(write_en),
        .instruction(instruction), .rdata(rdata), .misaligned(misaligned),
        .write_performed(write_performed), .byte_data(byte_data),
        .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(1'b0),
        .frame_done(frame_done), .frame_done_id(32'd1), .frame_statistics(416'b0),
        .buttons(8'b0),
        .frame_pending(frame_pending), .error_flags(error_flags), .scratch(scratch)
    );
    graphics_command_stream_decoder decoder (
        .clk(~clk), .reset(reset), .byte_data(byte_data), .byte_valid(byte_valid),
        .byte_ready(byte_ready), .command_data(command_data),
        .command_valid(command_valid), .command_ready(command_ready),
        .decoder_error(decoder_error)
    );
    always @(negedge clk) begin
        if (!reset) begin
            cycles <= cycles + 1;
            frame_done <= 0;
            // Exercise command backpressure as firmware continues to enqueue bytes.
            command_ready <= (cycles % 11) < 7;
            if (command_valid && command_ready) begin
                case (commands)
                    0: if (command_data.opcode != GFX_CMD_SET_PALETTE ||
                           `GFX_ARGUMENT(command_data) != 32'h01ff5020) $fatal(1, "Palette");
                    1: if (command_data.opcode != GFX_CMD_SET_VIEW_MATRIX ||
                           `GFX_VIEW_MATRIX(command_data) !=
                           192'h010000000000000000000100000000000000000001000000) $fatal(1, "View");
                    2: if (command_data.opcode != GFX_CMD_BEGIN_FRAME ||
                           `GFX_ARGUMENT(command_data) != 1) $fatal(1, "Frame ID");
                    3: if (command_data.opcode != GFX_CMD_DRAW_TRIANGLE ||
                           `GFX_TRIANGLE(command_data) !=
                           152'hff00ff0004000000010004000100ff00040001) $fatal(1, "Triangle");
                    4: begin
                        if (command_data.opcode != GFX_CMD_END_FRAME) $fatal(1, "End frame");
                        frame_done <= 1;
                    end
                    default: $fatal(1, "Unexpected command");
                endcase
                commands <= commands + 1;
            end
        end
    end
    initial begin
        repeat (5) @(posedge clk); #1; reset = 0;
        for (integer i = 0; i < 200000; i = i + 1) begin
            @(posedge clk); #1;
            if (error_flags != 0 || scratch == 32'hdead0001) $fatal(1, "Firmware/stream error");
            if (scratch == 1) begin
                if (commands != 5 || frame_pending) $fatal(1, "Completion/ACK");
                $display("PASS cpu_stream_tb (%0d cycles)", cycles); $finish;
            end
        end
        $fatal(1, "CPU stream timeout PC=%h", pc);
    end
endmodule
