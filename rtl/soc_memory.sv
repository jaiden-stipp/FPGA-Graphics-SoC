// Preserve the upstream falling-edge RAM and subword semantics.
module soc_memory #(
    parameter HEX_FILE = "build/firmware.hex",
    parameter MIF_FILE = "build/firmware.mif",
    parameter ENABLE_SDRAM = 0,
    parameter ENABLE_CACHE = 1,
    parameter ENABLE_BURST = 1,
    parameter CACHE_LINE_BYTES = 32
)(
    input logic clk, reset,
    input tri0 [159:0] cpu_statistics,
    input logic [31:0] pc, addr, wdata,
    input logic [2:0] funct3,
    input logic read_en, write_en,
    output logic [31:0] instruction, rdata,
    output logic misaligned, write_performed,
    output logic [7:0] byte_data,
    output logic byte_valid,
    input logic byte_ready,
    input logic decoder_error, command_error, frame_done,
    input logic [31:0] frame_done_id,
    input logic [415:0] frame_statistics,
    input logic [7:0] buttons,
    input tri0 [23:0] look_state,
    output logic frame_pending,
    output logic [3:0] error_flags,
    output logic [31:0] scratch,
    input tri0 sdram_reset, load_hold, load_valid, load_write,
    input tri0 [31:0] load_addr, load_wdata,
    output logic load_ready,
    output logic [31:0] load_rdata,
    output logic cpu_stall, sdram_initialized,
    output logic [31:0] refresh_count,
    output wire DRAM_CLK,
    output wire DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    output wire [12:0] DRAM_ADDR,
    output wire [1:0] DRAM_BA,
    output wire [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    localparam DMA_SUPPORTED=ENABLE_SDRAM && ENABLE_CACHE && ENABLE_BURST && CACHE_LINE_BYTES==32;
    wire dma_start,dma_busy,dma_valid,dma_accepted,dma_mem_valid,dma_mem_ready,dma_mem_response;
    wire[7:0]dma_byte,dma_error;
    wire[31:0]dma_source,dma_length,dma_id,dma_completed,dma_sent,dma_reads,dma_reqwait,dma_fifowait,dma_mem_data;
    wire[24:0]dma_mem_addr;
    logic ram_selected, ram_misaligned, ram_write, mmio_write;
    logic [31:0] ram_rdata, mmio_rdata;
    wire [191:0] cache_statistics;
    wire [31:0] bus_addr = load_hold ? load_addr : addr;
    wire [31:0] bus_wdata = load_hold ? load_wdata : wdata;
    wire [2:0] bus_funct3 = load_hold ? 3'b010 : funct3;
    wire bus_read = load_hold ? load_valid && !load_write : read_en && !reset;
    wire bus_write = load_hold ? load_valid && load_write : write_en && !reset;
    wire sdram_selected = ENABLE_SDRAM && bus_addr[31:27] == 5'b10000;
    logic ext_stall, ext_bad, ext_write;
    logic [31:0] ext_rdata;
    assign ram_selected = bus_addr < 32'h00010000;
    assign cpu_stall = !load_hold && ext_stall;
    assign load_ready = load_valid && (ram_selected || (sdram_selected && !ext_stall));
    assign load_rdata = ram_selected ? ram_rdata : ext_rdata;
    soc_ram #(.N(16384), .INIT_FILE(MIF_FILE), .HEX_FILE(HEX_FILE)) ram (
        .clk(clk), .pc(pc), .d_addr(bus_addr), .d_wdata(bus_wdata), .d_funct3(bus_funct3),
        .dw_en(bus_write && ram_selected),
        .dr_en(bus_read && ram_selected),
        .Instruction(instruction), .d_rdata(ram_rdata),
        .misaligned(ram_misaligned), .write_performed(ram_write)
    );
    soc_mmio #(.DMA_SUPPORTED(DMA_SUPPORTED)) mmio (
        .clk(~clk), .reset(reset), .addr(addr), .wdata(wdata), .funct3(funct3),
        .read_en(read_en && !ram_selected && !sdram_selected && !load_hold),
        .write_en(write_en && !ram_selected && !sdram_selected && !load_hold),
        .rdata(mmio_rdata), .write_performed(mmio_write),
        .byte_data(byte_data), .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(command_error),
        .frame_done(frame_done), .frame_done_id(frame_done_id),
        .frame_statistics(frame_statistics), .frame_pending(frame_pending),
        .buttons(buttons), .look_state(look_state),
        .cache_statistics(cache_statistics), .cpu_statistics(cpu_statistics),
        .error_flags(error_flags), .scratch(scratch),
        .dma_busy(dma_busy),.dma_byte_valid(dma_valid),.dma_byte_data(dma_byte),.dma_byte_accepted(dma_accepted),
        .dma_error_code(dma_error),.dma_completed_id(dma_completed),.dma_bytes_sent(dma_sent),.dma_read_words(dma_reads),.dma_request_wait(dma_reqwait),.dma_fifo_wait(dma_fifowait),
        .dma_start(dma_start),.dma_source(dma_source),.dma_length(dma_length),.dma_submission_id(dma_id)
    );
    assign rdata = ram_selected ? ram_rdata : sdram_selected ? ext_rdata : mmio_rdata;
    assign misaligned = ram_selected ? ram_misaligned : sdram_selected ? ext_bad :
                        ((read_en || write_en) && |addr[1:0]);
    assign write_performed = !load_hold && (ram_write || mmio_write || ext_write);
    generate if(DMA_SUPPORTED)begin : command_transfer
        gfx_command_dma dma(.clk(clk),.reset(sdram_reset),.cancel(load_hold || reset),.start(dma_start),
          .source(dma_source),.length(dma_length),.submission_id(dma_id),.busy(dma_busy),.error_code(dma_error),.completed_id(dma_completed),
          .bytes_sent(dma_sent),.read_words(dma_reads),.request_wait(dma_reqwait),.fifo_wait(dma_fifowait),
          .memory_valid(dma_mem_valid),.memory_address(dma_mem_addr),.memory_ready(dma_mem_ready),.memory_response_valid(dma_mem_response),.memory_response_data(dma_mem_data),
          .byte_valid(dma_valid),.byte_data(dma_byte),.byte_accepted(dma_accepted));
    end else begin
        assign {dma_busy,dma_valid,dma_mem_valid}=0;
        assign {dma_error,dma_completed,dma_sent,dma_reads,dma_reqwait,dma_fifowait,dma_byte,dma_mem_addr}=0;
    end endgenerate
    generate if (ENABLE_SDRAM) begin : external_memory
        logic req_valid, req_write, req_ready, response_valid;
        logic [24:0] req_addr;
        logic [31:0] req_data, response_data;
        logic [3:0] req_bytes;
        sdram_bridge bridge (
            .clk(clk), .reset(sdram_reset), .selected(sdram_selected),
            .read_en(bus_read), .write_en(bus_write), .addr(bus_addr), .wdata(bus_wdata),
            .funct3(bus_funct3), .rdata(ext_rdata), .stall(ext_stall),
            .misaligned(ext_bad), .write_performed(ext_write),
            .request_valid(req_valid), .request_write(req_write), .request_address(req_addr),
            .request_data(req_data), .request_byte_enable(req_bytes), .request_ready(req_ready),
            .response_valid(response_valid), .response_data(response_data)
        );
        logic mem_valid, mem_write, mem_burst, mem_ready, mem_response;
        logic [24:0] mem_addr;
        logic [31:0] mem_data, mem_rdata;
        logic [3:0] mem_bytes;
        if (ENABLE_CACHE) begin : cached
            wire [31:0] hits, misses, fills, writes, busy;
            assign cache_statistics = {32'h43410101,hits,misses,fills,writes,busy};
            sdram_cache #(.ENABLE_BURST(ENABLE_BURST), .CACHE_LINE_BYTES(CACHE_LINE_BYTES)) cache (
                .clk(clk), .reset(sdram_reset), .bypass(load_hold), .invalidate(load_hold || reset),
                .request_valid(req_valid), .request_write(req_write), .request_address(req_addr),
                .request_data(req_data), .request_byte_enable(req_bytes), .request_ready(req_ready),
                .response_valid(response_valid), .response_data(response_data),
                .memory_valid(mem_valid), .memory_write(mem_write), .memory_burst(mem_burst), .memory_address(mem_addr),
                .memory_data(mem_data), .memory_byte_enable(mem_bytes), .memory_ready(mem_ready),
                .memory_response_valid(mem_response), .memory_response_data(mem_rdata),
                .read_hits(hits), .read_misses(misses), .fill_words(fills),
                .write_requests(writes), .busy_cycles(busy)
            );
        end else begin : uncached
            assign cache_statistics = 0;
            assign mem_burst = 0;
            assign mem_valid=req_valid; assign mem_write=req_write; assign mem_addr=req_addr;
            assign mem_data=req_data; assign mem_bytes=req_bytes;
            assign req_ready=mem_ready; assign response_valid=mem_response; assign response_data=mem_rdata;
        end
        wire ctl_valid,ctl_write,ctl_burst,ctl_ready,ctl_response;
        wire[24:0]ctl_addr;wire[31:0]ctl_wdata,ctl_rdata;wire[3:0]ctl_bytes;
        sdram_command_arbiter #(.BURST_WORDS(CACHE_LINE_BYTES/4)) command_arbiter(
          .clk(clk),.reset(sdram_reset),.cpu_valid(mem_valid),.cpu_write(mem_write),.cpu_burst(mem_burst),.cpu_address(mem_addr),.cpu_data(mem_data),.cpu_bytes(mem_bytes),
          .cpu_ready(mem_ready),.cpu_response(mem_response),.cpu_rdata(mem_rdata),
          .dma_valid(dma_mem_valid),.dma_address(dma_mem_addr),.dma_ready(dma_mem_ready),.dma_response(dma_mem_response),.dma_rdata(dma_mem_data),
          .memory_valid(ctl_valid),.memory_write(ctl_write),.memory_burst(ctl_burst),.memory_address(ctl_addr),.memory_data(ctl_wdata),.memory_bytes(ctl_bytes),
          .memory_ready(ctl_ready),.memory_response(ctl_response),.memory_rdata(ctl_rdata));
        sdram_controller #(.ENABLE_BURST(ENABLE_BURST && ENABLE_CACHE), .CACHE_LINE_BYTES(CACHE_LINE_BYTES)) controller (
            .clk(clk), .reset(sdram_reset), .request_valid(ctl_valid), .request_write(ctl_write),
            .request_address(ctl_addr), .request_data(ctl_wdata), .request_byte_enable(ctl_bytes),
            .request_burst(ctl_burst),
            .request_ready(ctl_ready), .response_valid(ctl_response), .response_data(ctl_rdata),
            .initialized(sdram_initialized), .refresh_count(refresh_count),
            .DRAM_CLK(DRAM_CLK), .DRAM_CKE(DRAM_CKE), .DRAM_CS_N(DRAM_CS_N),
            .DRAM_RAS_N(DRAM_RAS_N), .DRAM_CAS_N(DRAM_CAS_N), .DRAM_WE_N(DRAM_WE_N),
            .DRAM_ADDR(DRAM_ADDR), .DRAM_BA(DRAM_BA), .DRAM_DQM(DRAM_DQM), .DRAM_DQ(DRAM_DQ)
        );
    end else begin : no_external_memory
        assign {dma_mem_ready,dma_mem_response,dma_mem_data}=0;
        assign cache_statistics = 0;
        assign {ext_stall,ext_bad,ext_write,sdram_initialized} = 4'b0001;
        assign ext_rdata = 0; assign refresh_count = 0;
        assign {DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} = 6'b001111;
        assign DRAM_ADDR = 0; assign DRAM_BA = 0; assign DRAM_DQM = 15;
    end endgenerate
endmodule
