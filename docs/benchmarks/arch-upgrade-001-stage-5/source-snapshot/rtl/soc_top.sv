`include "renderer_types.svh"

module soc_top #(
    parameter HEX_FILE = "build/firmware.hex",
    parameter MIF_FILE = "build/firmware.mif",
    parameter ENABLE_SDRAM = 0,
    parameter ENABLE_CACHE = 1,
    parameter ENABLE_BURST = 1,
    parameter CACHE_LINE_BYTES = 32
)(
    input logic clk, reset,
    input logic [7:0] buttons,
    input tri0 [23:0] look_state,
    output logic [31:0] debug_pc, scratch,
    output logic frame_pending,
    output logic [3:0] error_flags,
    output logic [7:0] VGA_R, VGA_G, VGA_B,
    output logic VGA_CLK, VGA_BLANK_N, VGA_SYNC_N, VGA_HS, VGA_VS,
    input tri0 sdram_reset, load_hold, load_valid, load_write,
    input tri0 [31:0] load_addr, load_wdata,
    output logic load_ready,
    output logic [31:0] load_rdata,
    output logic sdram_initialized,
    output logic [31:0] refresh_count,
    output wire DRAM_CLK,
    output wire DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    output wire [12:0] DRAM_ADDR,
    output wire [1:0] DRAM_BA,
    output wire [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    logic [31:0] addr, wdata, rdata;
    logic [31:0] instruction;
    logic [2:0] funct3;
    logic read_en, write_en, misaligned, write_performed;
    logic cpu_stall;
    wire [159:0] cpu_statistics;
    wire system_reset = reset || load_hold || (ENABLE_SDRAM && !sdram_initialized);
    logic [7:0] byte_data;
    logic byte_valid, byte_ready, decoder_error, command_error, frame_done;
    logic [31:0] frame_done_id;
    renderer_stats_t frame_statistics;

    RV32I_SoC cpu (
        .clk(clk), .rst(system_reset), .debug_pc(debug_pc), .soc_stall(cpu_stall),
        .soc_instruction(instruction), .soc_rdata(rdata),
        .soc_misaligned(misaligned), .soc_write_performed(write_performed),
        .soc_pc(), .soc_addr(addr), .soc_wdata(wdata), .soc_funct3(funct3),
        .soc_read_en(read_en), .soc_write_en(write_en), .cpu_statistics(cpu_statistics),
        .trace_valid(), .trace_pc(), .trace_instruction(), .trace_reg_write(),
        .trace_rd(), .trace_rd_data(), .trace_mem_read(), .trace_mem_write(),
        .trace_mem_address(), .trace_mem_data(), .trace_mem_funct3(),
        .trace_branch(), .trace_jump(), .trace_jalr(), .commit_valid()
    );
    soc_memory #(.HEX_FILE(HEX_FILE), .MIF_FILE(MIF_FILE), .ENABLE_SDRAM(ENABLE_SDRAM), .ENABLE_CACHE(ENABLE_CACHE), .ENABLE_BURST(ENABLE_BURST), .CACHE_LINE_BYTES(CACHE_LINE_BYTES)) memory (
        .clk(clk), .reset(system_reset), .cpu_statistics(cpu_statistics), .pc(debug_pc), .instruction(instruction),
        .sdram_reset(sdram_reset), .cpu_stall(cpu_stall),
        .load_hold(load_hold), .load_valid(load_valid), .load_write(load_write),
        .load_addr(load_addr), .load_wdata(load_wdata), .load_ready(load_ready), .load_rdata(load_rdata),
        .sdram_initialized(sdram_initialized), .refresh_count(refresh_count),
        .DRAM_CLK(DRAM_CLK), .DRAM_CKE(DRAM_CKE), .DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N), .DRAM_CAS_N(DRAM_CAS_N), .DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR), .DRAM_BA(DRAM_BA), .DRAM_DQM(DRAM_DQM), .DRAM_DQ(DRAM_DQ),
        .addr(addr), .wdata(wdata), .funct3(funct3), .read_en(read_en),
        .write_en(write_en), .rdata(rdata), .misaligned(misaligned),
        .write_performed(write_performed), .byte_data(byte_data),
        .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(command_error),
        .frame_done(frame_done), .frame_done_id(frame_done_id),
        .frame_statistics(frame_statistics), .frame_pending(frame_pending),
        .buttons(buttons), .look_state(look_state),
        .error_flags(error_flags), .scratch(scratch)
    );
    graphics_stream_renderer graphics (
        .clk(~clk), .reset(system_reset), .restart(1'b0),
        .reference_clk(clk),
        .byte_data(byte_data), .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(command_error),
        .frame_done(frame_done), .frame_done_id(frame_done_id),
        .frame_statistics(frame_statistics),
        .VGA_R(VGA_R), .VGA_G(VGA_G), .VGA_B(VGA_B), .VGA_CLK(VGA_CLK),
        .VGA_BLANK_N(VGA_BLANK_N), .VGA_SYNC_N(VGA_SYNC_N),
        .VGA_HS(VGA_HS), .VGA_VS(VGA_VS)
    );
endmodule
