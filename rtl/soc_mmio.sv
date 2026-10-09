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
    output logic frame_pending,
    output logic [3:0] error_flags,
    output logic [31:0] scratch
);
    localparam integer PTR_BITS = $clog2(FIFO_DEPTH);
    localparam integer COUNT_BITS = $clog2(FIFO_DEPTH + 1);
    logic [7:0] fifo [0:FIFO_DEPTH-1];
    logic [PTR_BITS-1:0] wr_ptr, rd_ptr;
    logic [COUNT_BITS-1:0] count;
    logic [31:0] last_frame_id;
    logic [415:0] stats_snapshot;
    logic selected, word_access, known_read, known_write, push, pop;
    logic [3:0] new_errors;
    logic [3:0] clear_errors;
    logic [7:0] buttons_meta, buttons_sync;
    logic [23:0] look_meta, look_sync;
    logic [31:0] cycles;

    // Arbitrary non-power-of-two depths are supported by explicit pointer wrap.
    // synthesis translate_off
    initial if (FIFO_DEPTH < 2) $fatal(1, "FIFO_DEPTH must be >= 2");
    // synthesis translate_on

    assign selected = addr[31:8] == 24'h400000;
    assign word_access = funct3 == 3'b010 && addr[1:0] == 0;
    assign known_write = addr[7:0] == 8'h00 || addr[7:0] == 8'h10 ||
                         addr[7:0] == 8'h14 || addr[7:0] == 8'h18;
    assign known_read = addr[7:0] == 8'h04 || addr[7:0] == 8'h08 ||
                        addr[7:0] == 8'h0c || addr[7:0] == 8'h14 ||
                        addr[7:0] == 8'h18 || addr[7:0] == 8'h1c ||
                        (addr[7:0] >= 8'h20 && addr[7:0] <= 8'h5c) || addr[7:0] == 8'h64;
    assign byte_data = fifo[rd_ptr];
    assign byte_valid = !reset && count != 0;
    assign pop = byte_valid && byte_ready;
    // Conservative full handling: a simultaneous pop does not authorize a full write.
    assign push = !reset && selected && word_access && write_en &&
                  addr[7:0] == 0 && count < FIFO_DEPTH;
    assign write_performed = !reset && selected && word_access && write_en &&
                             known_write && (addr[7:0] != 0 || count < FIFO_DEPTH);
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
                default: rdata = stats_snapshot[415 - ((addr[7:0]-8'h20)/4)*32 -: 32];
            endcase
        end
        new_errors = 0;
        if (!reset) begin
            new_errors[0] = selected && word_access && write_en &&
                            addr[7:0] == 0 && count == FIFO_DEPTH;
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
            cycles <= 0;
        end else begin
            buttons_meta <= buttons;
            buttons_sync <= buttons_meta;
            look_meta <= look_state; look_sync <= look_meta;
            cycles <= cycles + 1'b1;
            if (push) begin
                fifo[wr_ptr] <= wdata[7:0];
                if (wr_ptr == FIFO_DEPTH-1) wr_ptr <= '0;
                else wr_ptr <= wr_ptr + 1'b1;
            end
            if (pop) begin
                if (rd_ptr == FIFO_DEPTH-1) rd_ptr <= '0;
                else rd_ptr <= rd_ptr + 1'b1;
            end
            case ({push, pop})
                2'b10: count <= count + 1'b1;
                2'b01: count <= count - 1'b1;
                default: begin end
            endcase
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
endmodule
