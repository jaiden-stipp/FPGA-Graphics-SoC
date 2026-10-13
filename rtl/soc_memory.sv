// Preserve the upstream falling-edge RAM and subword semantics.
module soc_memory #(
    parameter HEX_FILE = "build/firmware.hex",
    parameter MIF_FILE = "build/firmware.mif",
    parameter ENABLE_SDRAM = 0,
    parameter ENABLE_CACHE = 1,
    parameter ENABLE_BURST = 1,
    parameter CACHE_LINE_BYTES = 32,
    parameter ENABLE_SDRAM_EXEC = 0
)(
    input logic clk, reset,
    input tri0 [159:0] cpu_statistics,
    input logic [31:0] pc, addr, wdata,
    input tri0 [31:0] fetch_next_pc,
    input tri0 fetch_lookahead_valid,
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
`ifdef SOC_DISABLE_COMMAND_DMA
    localparam DMA_SUPPORTED=0;
`else
    localparam DMA_SUPPORTED=ENABLE_SDRAM && ENABLE_CACHE && ENABLE_BURST && CACHE_LINE_BYTES==32 && !ENABLE_SDRAM_EXEC;
`endif
    wire dma_start,dma_busy,dma_valid,dma_accepted,dma_mem_valid,dma_mem_ready,dma_mem_response;
    wire[7:0]dma_byte,dma_error;
    wire[31:0]dma_source,dma_length,dma_id,dma_completed,dma_sent,dma_reads,dma_reqwait,dma_fifowait,dma_mem_data;
    wire[24:0]dma_mem_addr;
    logic ram_selected, ram_misaligned, ram_write, mmio_write;
    logic [31:0] ram_rdata, mmio_rdata;
    wire [191:0] cache_statistics;
    wire [127:0] instruction_statistics;
    wire [31:0] local_instruction,external_instruction;
    wire instruction_hit,instruction_request,instruction_ready,instruction_response;
    wire [24:0] instruction_address;
    wire [31:0] instruction_data;
    // First 16 MiB is immutable executable/constant storage on this capability.
    wire executable_pc=ENABLE_SDRAM_EXEC && pc>=32'h80000000 && pc<32'h81000000 && pc[1:0]==0;
    wire fetch_stall=executable_pc && !instruction_hit && !reset;
    wire fetch_fault=ENABLE_SDRAM_EXEC && !reset && !(pc[1:0]==0 && (pc<32'h10000 || executable_pc));
    wire code_store_fault=ENABLE_SDRAM_EXEC && !reset && !load_hold && write_en && addr>=32'h80000000 && addr<32'h81000000;
    wire local_access_ready=!ENABLE_SDRAM_EXEC || !(fetch_stall || fetch_fault || code_store_fault);
    wire [31:0] bus_addr = load_hold ? load_addr : addr;
    wire [31:0] bus_wdata = load_hold ? load_wdata : wdata;
    wire [2:0] bus_funct3 = load_hold ? 3'b010 : funct3;
    wire bus_read = load_hold ? load_valid && !load_write : read_en && !reset;
    wire bus_write = load_hold ? load_valid && load_write : write_en && !reset && !code_store_fault;
    wire sdram_selected = ENABLE_SDRAM && bus_addr[31:27] == 5'b10000;
    logic ext_stall, ext_bad, ext_write;
    logic [31:0] ext_rdata;
    assign ram_selected = bus_addr < 32'h00010000;
    assign cpu_stall = !load_hold && (ext_stall || fetch_stall || fetch_fault || code_store_fault);
    assign load_ready = load_valid && (ram_selected || (sdram_selected && !ext_stall));
    assign load_rdata = ram_selected ? ram_rdata : ext_rdata;
    soc_ram #(.N(16384), .INIT_FILE(MIF_FILE), .HEX_FILE(HEX_FILE),.READ_DURING_WRITE_MODE(ENABLE_SDRAM_EXEC?"OLD_DATA":"NEW_DATA_NO_NBE_READ")) ram (
        .clk(clk), .pc(pc), .d_addr(bus_addr), .d_wdata(bus_wdata), .d_funct3(bus_funct3),
        .dw_en(bus_write && ram_selected && (load_hold || local_access_ready)),
        .dr_en(bus_read && ram_selected),
        .Instruction(local_instruction), .d_rdata(ram_rdata),
        .misaligned(ram_misaligned), .write_performed(ram_write)
    );
    assign instruction=executable_pc?external_instruction:local_instruction;
    generate if(ENABLE_SDRAM_EXEC)begin : instruction_fetch
        initial if(!ENABLE_SDRAM || !ENABLE_CACHE || !ENABLE_BURST || CACHE_LINE_BYTES!=32)
            $fatal(1,"SDRAM execution requires SDRAM, BL8 and 32-byte data-cache lines");
        wire [31:0] hits,misses,fills;
        assign instruction_statistics={32'h49430101,hits,misses,fills};
        sdram_instruction_cache cache(.clk(clk),.reset(sdram_reset),.invalidate(reset || load_hold),
            .selected(executable_pc && !reset && !load_hold),.advance(!cpu_stall),.pc(pc),.next_pc(instruction_hit && fetch_lookahead_valid?fetch_next_pc:pc),
            .hit(instruction_hit),.instruction(external_instruction),
            .request_valid(instruction_request),.request_address(instruction_address),
            .request_ready(instruction_ready),.response_valid(instruction_response),.response_data(instruction_data),
            .read_hits(hits),.read_misses(misses),.fill_words(fills));
    end else begin
        assign instruction_hit=0;assign external_instruction=0;
        assign instruction_request=0;assign instruction_address=0;assign instruction_statistics=0;
    end endgenerate
    wire [31:0] geometry_rdata;
    wire geometry_write;
`ifdef SOC_GEOMETRY_WORKER
    wire geometry_selected=addr[31:8]==24'h400001 && !load_hold;
    geometry_worker geometry(.clk(~clk),.reset(reset || load_hold),.addr(addr),.wdata(wdata),
        .funct3(funct3),.read_en(read_en && geometry_selected && local_access_ready),.write_en(write_en && geometry_selected && local_access_ready),
        .rdata(geometry_rdata),.write_performed(geometry_write));
`else
    wire geometry_selected=0;
    assign geometry_rdata=0,geometry_write=0;
`endif
    soc_mmio #(.DMA_SUPPORTED(DMA_SUPPORTED),.SDRAM_EXEC_SUPPORTED(ENABLE_SDRAM_EXEC)) mmio (
        .clk(~clk), .reset(reset), .addr(addr), .wdata(wdata), .funct3(funct3),
        .read_en(read_en && !ram_selected && !sdram_selected && !geometry_selected && !load_hold && local_access_ready),
        .write_en(write_en && !ram_selected && !sdram_selected && !geometry_selected && !load_hold && local_access_ready),
        .rdata(mmio_rdata), .write_performed(mmio_write),
        .byte_data(byte_data), .byte_valid(byte_valid), .byte_ready(byte_ready),
        .decoder_error(decoder_error), .command_error(command_error),
        .frame_done(frame_done), .frame_done_id(frame_done_id),
        .frame_statistics(frame_statistics), .frame_pending(frame_pending),
        .buttons(buttons), .look_state(look_state),
        .cache_statistics(cache_statistics), .cpu_statistics(cpu_statistics),
        .instruction_statistics(instruction_statistics),.external_fault(fetch_fault || code_store_fault),
        .error_flags(error_flags), .scratch(scratch),
        .dma_busy(dma_busy),.dma_byte_valid(dma_valid),.dma_byte_data(dma_byte),.dma_byte_accepted(dma_accepted),
        .dma_error_code(dma_error),.dma_completed_id(dma_completed),.dma_bytes_sent(dma_sent),.dma_read_words(dma_reads),.dma_request_wait(dma_reqwait),.dma_fifo_wait(dma_fifowait),
        .dma_start(dma_start),.dma_source(dma_source),.dma_length(dma_length),.dma_submission_id(dma_id)
    );
    assign rdata = ram_selected ? ram_rdata : sdram_selected ? ext_rdata : geometry_selected ? geometry_rdata : mmio_rdata;
    assign misaligned = ram_selected ? ram_misaligned : sdram_selected ? ext_bad :
                        ((read_en || write_en) && |addr[1:0]);
    assign write_performed = !load_hold && (ram_write || mmio_write || ext_write || geometry_write);
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
        if(ENABLE_SDRAM_EXEC)begin : executable_bridge
        sdram_execution_bridge bridge (
            .clk(clk),.reset(sdram_reset),.cpu_reset(reset),.load_hold(load_hold),.load_valid(load_valid),.advance(!cpu_stall),
            .selected(sdram_selected),.read_en(bus_read),.write_en(bus_write),.addr(bus_addr),.wdata(bus_wdata),.funct3(bus_funct3),
            .rdata(ext_rdata),.stall(ext_stall),.misaligned(ext_bad),.write_performed(ext_write),
            .request_valid(req_valid),.request_write(req_write),.request_address(req_addr),.request_data(req_data),.request_byte_enable(req_bytes),
            .request_ready(req_ready),.response_valid(response_valid),.response_data(response_data));
        end else begin : local_code_bridge
        sdram_bridge bridge (
            .clk(clk), .reset(sdram_reset), .selected(sdram_selected),
            .read_en(bus_read), .write_en(bus_write), .addr(bus_addr), .wdata(bus_wdata),
            .funct3(bus_funct3), .rdata(ext_rdata), .stall(ext_stall),
            .misaligned(ext_bad), .write_performed(ext_write),
            .request_valid(req_valid), .request_write(req_write), .request_address(req_addr),
            .request_data(req_data), .request_byte_enable(req_bytes), .request_ready(req_ready),
            .response_valid(response_valid), .response_data(response_data)
        );
        end
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
`ifdef SOC_DISABLE_COMMAND_DMA
        // Accepted Stage 2A topology: cache connects directly to the controller.
        assign ctl_valid=mem_valid;assign ctl_write=mem_write;assign ctl_burst=mem_burst;
        assign ctl_addr=mem_addr;assign ctl_wdata=mem_data;assign ctl_bytes=mem_bytes;
        assign mem_ready=ctl_ready;assign mem_response=ctl_response;assign mem_rdata=ctl_rdata;
        assign {dma_mem_ready,dma_mem_response,dma_mem_data}=0;
`else
        sdram_command_arbiter #(.BURST_WORDS(CACHE_LINE_BYTES/4)) command_arbiter(
          .clk(clk),.reset(sdram_reset),.cpu_valid(mem_valid),.cpu_write(mem_write),.cpu_burst(mem_burst),.cpu_address(mem_addr),.cpu_data(mem_data),.cpu_bytes(mem_bytes),
          .cpu_ready(mem_ready),.cpu_response(mem_response),.cpu_rdata(mem_rdata),
          .dma_valid(dma_mem_valid),.dma_address(dma_mem_addr),.dma_ready(dma_mem_ready),.dma_response(dma_mem_response),.dma_rdata(dma_mem_data),
          .memory_valid(ctl_valid),.memory_write(ctl_write),.memory_burst(ctl_burst),.memory_address(ctl_addr),.memory_data(ctl_wdata),.memory_bytes(ctl_bytes),
          .memory_ready(ctl_ready),.memory_response(ctl_response),.memory_rdata(ctl_rdata));
`endif
        wire final_valid,final_write,final_burst,final_ready,final_response;
        wire [24:0] final_addr;wire [31:0] final_wdata,final_rdata;wire [3:0] final_bytes;
        if(ENABLE_SDRAM_EXEC)begin : fetch_arbitration
            sdram_fetch_arbiter arbiter(.clk(clk),.reset(sdram_reset),
                .instruction_valid(instruction_request),.instruction_address(instruction_address),
                .instruction_ready(instruction_ready),.instruction_response(instruction_response),.instruction_data(instruction_data),
                .data_valid(ctl_valid),.data_write(ctl_write),.data_burst(ctl_burst),.data_address(ctl_addr),.data_wdata(ctl_wdata),.data_bytes(ctl_bytes),
                .data_ready(ctl_ready),.data_response(ctl_response),.data_rdata(ctl_rdata),
                .memory_valid(final_valid),.memory_write(final_write),.memory_burst(final_burst),.memory_address(final_addr),
                .memory_data(final_wdata),.memory_bytes(final_bytes),.memory_ready(final_ready),.memory_response(final_response),.memory_rdata(final_rdata));
        end else begin
            assign final_valid=ctl_valid;assign final_write=ctl_write;assign final_burst=ctl_burst;
            assign final_addr=ctl_addr;assign final_wdata=ctl_wdata;assign final_bytes=ctl_bytes;
            assign ctl_ready=final_ready;assign ctl_response=final_response;assign ctl_rdata=final_rdata;
            assign instruction_ready=0;assign instruction_response=0;assign instruction_data=0;
        end
        sdram_controller #(.ENABLE_BURST(ENABLE_BURST && ENABLE_CACHE), .CACHE_LINE_BYTES(CACHE_LINE_BYTES)) controller (
            .clk(clk), .reset(sdram_reset), .request_valid(final_valid), .request_write(final_write),
            .request_address(final_addr), .request_data(final_wdata), .request_byte_enable(final_bytes),
            .request_burst(final_burst),
            .request_ready(final_ready), .response_valid(final_response), .response_data(final_rdata),
            .initialized(sdram_initialized), .refresh_count(refresh_count),
            .DRAM_CLK(DRAM_CLK), .DRAM_CKE(DRAM_CKE), .DRAM_CS_N(DRAM_CS_N),
            .DRAM_RAS_N(DRAM_RAS_N), .DRAM_CAS_N(DRAM_CAS_N), .DRAM_WE_N(DRAM_WE_N),
            .DRAM_ADDR(DRAM_ADDR), .DRAM_BA(DRAM_BA), .DRAM_DQM(DRAM_DQM), .DRAM_DQ(DRAM_DQ)
        );
    end else begin : no_external_memory
        assign instruction_ready=0;assign instruction_response=0;assign instruction_data=0;
        assign {dma_mem_ready,dma_mem_response,dma_mem_data}=0;
        assign cache_statistics = 0;
        assign {ext_stall,ext_bad,ext_write,sdram_initialized} = 4'b0001;
        assign ext_rdata = 0; assign refresh_count = 0;
        assign {DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N} = 6'b001111;
        assign DRAM_ADDR = 0; assign DRAM_BA = 0; assign DRAM_DQM = 15;
    end endgenerate
endmodule
