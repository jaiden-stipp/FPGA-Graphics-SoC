// Blocking 4 KiB direct-mapped data cache; selectable 8/16/32-byte lines.
// Write-through, no write allocation. Burst length matches the selected line.
// Addresses are SDRAM-relative WORD addresses, not CPU byte addresses.
module execution_data_cache #(parameter ENABLE_BURST = 1, parameter CACHE_LINE_BYTES = 32, parameter CACHE_BYTES=4096) (
    input logic clk, reset, bypass, invalidate,
    input logic request_valid, request_write,
    input logic [24:0] request_address,
    input logic [31:0] request_data,
    input logic [3:0] request_byte_enable,
    output logic request_ready, response_valid,
    output logic [31:0] response_data,
    output logic memory_valid, memory_write, memory_burst,
    output logic [24:0] memory_address,
    output logic [31:0] memory_data,
    output logic [3:0] memory_byte_enable,
    input logic memory_ready, memory_response_valid,
    input logic [31:0] memory_response_data,
    output logic [31:0] read_hits, read_misses, fill_words, write_requests,
    output logic [31:0] busy_cycles
);
    localparam WORD_COUNT=CACHE_BYTES/4; localparam WORD_BITS=$clog2(WORD_COUNT);
    localparam LINE_WORDS = CACHE_LINE_BYTES / 4;
    localparam OFFSET_BITS = $clog2(LINE_WORDS);
    localparam LINE_COUNT = WORD_COUNT / LINE_WORDS;
    initial if (CACHE_LINE_BYTES != 8 && CACHE_LINE_BYTES != 16 && CACHE_LINE_BYTES != 32)
        $fatal(1,"CACHE_LINE_BYTES must be 8, 16 or 32");
    typedef enum logic [2:0] {IDLE, LOOKUP, ISSUE, WAIT_MEMORY} state_t;
    state_t state;
    (* ramstyle = "M9K" *) logic [31:0] words [0:WORD_COUNT-1];
    logic [24-WORD_BITS:0] tags [0:LINE_COUNT-1];
    logic [LINE_COUNT-1:0] valid;
    logic [24:0] saved_address;
    logic [31:0] saved_data, lookup_data, critical_data;
    logic [3:0] saved_bytes;
    logic saved_write, saved_bypass, filling, discard_fill;
    logic [OFFSET_BITS-1:0] fill_offset;
    wire [WORD_BITS-1-OFFSET_BITS:0] line_index = saved_address[WORD_BITS-1:OFFSET_BITS];
    wire [24-WORD_BITS:0] tag = saved_address[24:WORD_BITS];
    wire hit = valid[line_index] && tags[line_index] == tag;
    wire filling_word = state == WAIT_MEMORY && memory_response_valid && filling;
    wire storing_hit = state == LOOKUP && saved_write && !saved_bypass && !invalidate && hit;
    wire [WORD_BITS-1:0] ram_write_address = filling_word ? {line_index,fill_offset} : saved_address[WORD_BITS-1:0];
    wire [31:0] ram_write_data = filling_word ? memory_response_data : saved_data;
    wire [3:0] ram_write_bytes = filling_word ? 4'b1111 : saved_bytes;
    // A single byte-enabled write port and unconditional synchronous read let
    // Quartus infer block RAM rather than thousands of data flip-flops.
    always_ff @(posedge clk) begin
        lookup_data <= words[request_address[WORD_BITS-1:0]];
        for (integer b=0;b<4;b=b+1)
            if (!reset && (filling_word || storing_hit) && ram_write_bytes[b])
                words[ram_write_address][8*b +: 8] <= ram_write_data[8*b +: 8];
    end
    assign request_ready = state == IDLE;
    assign memory_valid = state == ISSUE;
    assign memory_write = saved_write;
    assign memory_burst = ENABLE_BURST && filling;
    assign memory_address = filling ? {saved_address[24:OFFSET_BITS],(ENABLE_BURST ? {OFFSET_BITS{1'b0}} : fill_offset)} : saved_address;
    assign memory_data = saved_data;
    assign memory_byte_enable = saved_bytes;
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= IDLE; valid <= 0; response_valid <= 0; response_data <= 0;
            saved_address <= 0; saved_data <= 0; saved_bytes <= 0;
            saved_write <= 0; saved_bypass <= 0; filling <= 0;
            discard_fill <= 0; fill_offset <= 0; critical_data <= 0;
            read_hits <= 0; read_misses <= 0; fill_words <= 0;
            write_requests <= 0; busy_cycles <= 0;
        end else begin
            response_valid <= 0;
            if (state != IDLE) busy_cycles <= busy_cycles + 1'b1;
            // Invalidation never aborts a controller transaction. A fill already
            // in flight drains but cannot install stale data after loading starts.
            if (invalidate) begin valid <= 0; discard_fill <= 1; end
            case (state)
                IDLE: if (request_valid) begin
                    saved_address <= request_address; saved_data <= request_data;
                    saved_bytes <= request_byte_enable; saved_write <= request_write;
                    saved_bypass <= bypass || invalidate;
                    discard_fill <= invalidate; filling <= 0; fill_offset <= 0;
                    state <= LOOKUP;
                end
                LOOKUP: begin
                    if (saved_write) begin
                        write_requests <= write_requests + 1'b1;
                        state <= ISSUE;
                    end else if (!saved_bypass && !invalidate && hit) begin
                        read_hits <= read_hits + 1'b1;
                        response_data <= lookup_data; response_valid <= 1; state <= IDLE;
                    end else begin
                        if (!saved_bypass && !invalidate) begin
                            read_misses <= read_misses + 1'b1;
                            valid[line_index] <= 0; filling <= 1;
                        end
                        state <= ISSUE;
                    end
                end
                ISSUE: if (memory_ready) state <= WAIT_MEMORY;
                WAIT_MEMORY: if (memory_response_valid) begin
                    if (filling) begin
                        fill_words <= fill_words + 1'b1;
                        if (fill_offset == saved_address[OFFSET_BITS-1:0]) critical_data <= memory_response_data;
                        if (fill_offset == LINE_WORDS-1) begin
                            if (!discard_fill && !invalidate) begin
                                valid[line_index] <= 1; tags[line_index] <= tag;
                            end
                            response_data <= saved_address[OFFSET_BITS-1:0] == LINE_WORDS-1 ? memory_response_data : critical_data;
                            response_valid <= 1; state <= IDLE;
                        end else begin
                            fill_offset <= fill_offset + 1'b1;
                            state <= ENABLE_BURST ? WAIT_MEMORY : ISSUE;
                        end
                    end else begin
                        response_data <= memory_response_data; response_valid <= 1; state <= IDLE;
                    end
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
