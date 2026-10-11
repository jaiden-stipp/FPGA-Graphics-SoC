// Peripheral clock is the inverted CPU clock: transactions commit at CPU negedge.
// A request occupies one MEM stage cycle; there is no wait-state interface.
module soc_mmio #(
    parameter integer FIFO_DEPTH = 256,
    parameter integer CLOCK_HZ = 50000000
)(
    input logic clk, reset,
    input logic [31:0] addr, wdata,
    input logic [2:0] funct3,
    input logic read_en, write_en,
    output logic [31:0] rdata,
    output logic write_performed,
    output logic [7:0] byte_data,
    output logic byte_valid,
    input logic byte_ready,
    input logic decoder_error, command_error, frame_done,
    input logic [31:0] frame_done_id,
    input logic [415:0] frame_statistics,
    input logic [7:0] buttons,
    input tri0 [23:0] look_state,
    input tri0 [191:0] cache_statistics,
    input tri0 [159:0] cpu_statistics,
    output logic frame_pending,
    output logic [3:0] error_flags,
    output logic [31:0] scratch
);
    localparam integer PTR_BITS = $clog2(FIFO_DEPTH);
    localparam integer COUNT_BITS = $clog2(FIFO_DEPTH + 1);
    logic [PTR_BITS-1:0] wr_ptr, rd_ptr;
    logic [COUNT_BITS-1:0] count;
    logic [31:0] last_frame_id;
    logic [415:0] stats_snapshot;
    logic selected, word_access, known_read, known_write, push, pop;
    logic packed_address, enqueue_address;
    logic [2:0] requested_bytes, push_bytes;
    logic [3:0] new_errors;
    logic [3:0] clear_errors;
    logic [7:0] buttons_meta, buttons_sync;
    logic [23:0] look_meta, look_sync;
    logic [31:0] cycles, status_reads, full_status_reads;
    logic [223:0] cpu_snapshot;


    // Arbitrary non-power-of-two depths are supported by explicit pointer wrap.
    // synthesis translate_off
    initial if (FIFO_DEPTH < 2) $fatal(1, "FIFO_DEPTH must be >= 2");
    // synthesis translate_on

    assign selected = addr[31:8] == 24'h400000;
    assign word_access = funct3 == 3'b010 && addr[1:0] == 0;
    assign known_write = addr[7:0] == 8'h00 || addr[7:0] == 8'h10 ||
                         addr[7:0] == 8'h14 || addr[7:0] == 8'h18 || addr[7:0] == 8'h98 || packed_address;
    assign known_read = addr[7:0] == 8'h04 || addr[7:0] == 8'h08 ||
                        addr[7:0] == 8'h0c || addr[7:0] == 8'h14 ||
                        addr[7:0] == 8'h18 || addr[7:0] == 8'h1c ||
                        (addr[7:0] >= 8'h20 && addr[7:0] <= 8'h5c) || addr[7:0] == 8'h64 ||
                        (addr[7:0] >= 8'h68 && addr[7:0] <= 8'h94) || addr[7:0] == 8'h9c || addr[7:0] == 8'ha0 || addr[7:0] == 8'ha4 || addr[7:0] == 8'ha8;
    // Packed offsets b0/b4/b8/bc enqueue 1/2/3/4 bytes, low byte first.
    // Availability is conservative: a concurrent pop grants no reservation.
    assign packed_address = addr[7:4] == 4'hb;
    assign enqueue_address = addr[7:0] == 0 || packed_address;
    assign requested_bytes = packed_address ? {1'b0,addr[3:2]} + 3'd1 : 3'd1;
    assign byte_valid = !reset && count != 0;
    assign pop = byte_valid && byte_ready;
    // Conservative full handling: a simultaneous pop does not authorize a full write.
    assign push = !reset && selected && word_access && write_en &&
                  enqueue_address && FIFO_DEPTH-count >= requested_bytes;
    assign push_bytes = push ? requested_bytes : 3'd0;
    assign write_performed = !reset && selected && word_access && write_en &&
                             known_write && (!enqueue_address || FIFO_DEPTH-count >= requested_bytes);
    assign clear_errors = write_performed && addr[7:0] == 8'h14 ? wdata[3:0] : 4'b0;

    always_comb begin
        rdata = 0;
        if (!reset && selected && word_access && read_en && known_read) begin
            case (addr[7:0])
                8'h04: rdata = {28'b0, (|error_flags), frame_pending,
                                (count == 0), (count < FIFO_DEPTH)};
                8'h08: rdata = FIFO_DEPTH - count;
                8'h0c: rdata = last_frame_id;
                8'h14: rdata = {28'b0, error_flags};
                8'h18: rdata = scratch;
                8'h1c: rdata = 32'h534f4301;
                8'h54: rdata = {look_sync, buttons_sync};
                8'h58: rdata = cycles;
                8'h5c: rdata = CLOCK_HZ;
                8'h64: rdata = 32'h494e0101;
                8'h68: rdata = cache_statistics[191:160];
                8'h6c: rdata = cache_statistics[159:128];
                8'h70: rdata = cache_statistics[127:96];
                8'h74: rdata = cache_statistics[95:64];
                8'h78: rdata = cache_statistics[63:32];
                8'h7c: rdata = cache_statistics[31:0];
                8'h80: rdata = 32'h43500101;
                8'h84: rdata = cpu_snapshot[223:192];
                8'h88: rdata = cpu_snapshot[191:160];
                8'h8c: rdata = cpu_snapshot[159:128];
                8'h90: rdata = cpu_snapshot[127:96];
                8'h94: rdata = cpu_snapshot[95:64];
                8'h9c: rdata = 32'h80000001; // MUL and GPU capability-register presence
                8'ha0: rdata = cpu_snapshot[63:32];
                8'ha4: rdata = cpu_snapshot[31:0];
                8'ha8: rdata = 32'h00000003; // fractional mesh and packed-enqueue-v1
                default: rdata = stats_snapshot[415 - ((addr[7:0]-8'h20)/4)*32 -: 32];
            endcase
        end
        new_errors = 0;
        if (!reset) begin
            new_errors[0] = selected && word_access && write_en &&
                            enqueue_address && FIFO_DEPTH-count < requested_bytes;
            new_errors[1] = decoder_error;
            new_errors[2] = command_error;
            new_errors[3] = (read_en || write_en) &&
                (!selected || !word_access || (read_en && !known_read) ||
                 (write_en && !known_write));
        end
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            count <= 0;
            error_flags <= 0;
            frame_pending <= 0;
            last_frame_id <= 0;
            stats_snapshot <= 0;
            scratch <= 0;
            buttons_meta <= 0;
            buttons_sync <= 0;
            look_meta <= 0; look_sync <= 0;
            cycles <= 0; status_reads <= 0; full_status_reads <= 0; cpu_snapshot <= 0;
        end else begin
            buttons_meta <= buttons;
            buttons_sync <= buttons_meta;
            look_meta <= look_state; look_sync <= look_meta;
            cycles <= cycles + 1'b1;
            if (selected && word_access && read_en && addr[7:0] == 8'h04) begin
                status_reads <= status_reads + 1'b1;
                if (count == FIFO_DEPTH) full_status_reads <= full_status_reads + 1'b1;
            end
            // Same-clock opposite edge sampling; hold all fields until the next request.
            if (write_performed && addr[7:0] == 8'h98 && wdata[0])
                cpu_snapshot <= {cpu_statistics,status_reads,full_status_reads};
            if (push) wr_ptr <= advance_pointer(wr_ptr,push_bytes);
            if (pop) begin
                if (rd_ptr == FIFO_DEPTH-1) rd_ptr <= '0;
                else rd_ptr <= rd_ptr + 1'b1;
            end
            if(push || pop) count <= count + push_bytes - (pop ? 1'b1 : 1'b0);
            // New events win over software acknowledgements on the same edge.
            error_flags <= (error_flags & ~clear_errors) | new_errors;
            if (write_performed && addr[7:0] == 8'h10 && wdata[0])
                frame_pending <= 0;
            if (frame_done) begin
                frame_pending <= 1;
                last_frame_id <= frame_done_id;
                stats_snapshot <= frame_statistics;
            end
            if (write_performed && addr[7:0] == 8'h18) scratch <= wdata;
        end
    end

    function automatic [PTR_BITS-1:0] advance_pointer(
        input logic [PTR_BITS-1:0] pointer, input logic [2:0] amount);
        integer position;
        begin
            position = pointer + amount;
            if(position >= FIFO_DEPTH) position = position - FIFO_DEPTH;
            advance_pointer = position;
        end
    endfunction

    // Four independently written banks preserve FIFO capacity and one-byte
    // consumer bandwidth. A packed enqueue writes at most once in each bank.
    genvar b;
    generate if(FIFO_DEPTH >= 4 && FIFO_DEPTH % 4 == 0) begin : banked
        localparam integer BANK_DEPTH = FIFO_DEPTH / 4;
        localparam integer BANK_BITS = BANK_DEPTH > 1 ? $clog2(BANK_DEPTH) : 1;
        wire [7:0] bank_read [0:3];
        for(b=0;b<4;b=b+1) begin : bank
            logic [7:0] storage [0:BANK_DEPTH-1];
            logic [1:0] offset;
            logic [BANK_BITS-1:0] write_row;
            integer row;
            always_comb begin
                offset = b - wr_ptr[1:0];
                row = (wr_ptr >> 2) + (b < wr_ptr[1:0] ? 1 : 0);
                if(row == BANK_DEPTH) row = 0;
                write_row = row;
            end
            assign bank_read[b] = storage[rd_ptr >> 2];
            always_ff @(posedge clk) begin
                if(!reset && push && {1'b0,offset} < push_bytes)
                    storage[write_row] <= wdata[offset*8+:8];
            end
        end
        assign byte_data = bank_read[rd_ptr[1:0]];
    end else begin : arbitrary_depth
        // Preserve small/non-multiple-of-four verification configurations.
        logic [7:0] storage [0:FIFO_DEPTH-1];
        integer position;
        assign byte_data = storage[rd_ptr];
        always_ff @(posedge clk) begin
            if(!reset && push)
                for(integer j=0;j<4;j=j+1) begin
                    position = wr_ptr + j;
                    if(position >= FIFO_DEPTH) position = position - FIFO_DEPTH;
                    if(j < push_bytes) storage[position] <= wdata >> (j*8);
                end
        end
    end endgenerate
endmodule
