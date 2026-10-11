// Hold MEM and every pipeline register until the SDRAM transaction completes.
// Requests/results are latched on the original CPU memory (falling) edge.
module sdram_bridge (
    input logic clk, reset, selected, read_en, write_en,
    input logic [31:0] addr, wdata,
    input logic [2:0] funct3,
    output logic [31:0] rdata,
    output logic stall, misaligned, write_performed,
    output logic request_valid, request_write,
    output logic [24:0] request_address,
    output logic [31:0] request_data,
    output logic [3:0] request_byte_enable,
    input logic request_ready, response_valid,
    input logic [31:0] response_data
);
    logic pending, completed, access_bad;
    logic [2:0] saved_funct3;
    logic [1:0] saved_lane;
    logic [31:0] shifted;
    always_comb begin
        access_bad = 0;
        case (funct3)
            3'b000,3'b100: access_bad = write_en && funct3[2];
            3'b001,3'b101: access_bad = addr[0] || (write_en && funct3[2]);
            3'b010: access_bad = |addr[1:0];
            default: access_bad = 1;
        endcase
    end
    assign misaligned = selected && (read_en || write_en) && access_bad;
    assign stall = selected && (read_en || write_en) && !access_bad && !completed;
    assign request_valid = pending;
    always_ff @(negedge clk) begin
        if (reset) begin
            pending <= 0; completed <= 0; rdata <= 0;
            write_performed <= 0; request_write <= 0; request_address <= 0;
            request_data <= 0; request_byte_enable <= 0; saved_funct3 <= 0; saved_lane <= 0;
        end else begin
            write_performed <= 0;
            if (completed) completed <= 0;
            else if (!pending && selected && (read_en || write_en) && !access_bad) begin
                pending <= 1; request_write <= write_en;
                request_address <= addr[26:2]; request_data <= wdata << (8*addr[1:0]);
                saved_funct3 <= funct3; saved_lane <= addr[1:0];
                case (funct3[1:0])
                    0: request_byte_enable <= 4'b0001 << addr[1:0];
                    1: request_byte_enable <= 4'b0011 << addr[1:0];
                    default: request_byte_enable <= 4'b1111;
                endcase
            end
            if (pending && response_valid) begin
                shifted = response_data >> (8*saved_lane);
                case (saved_funct3)
                    3'b000: rdata <= {{24{shifted[7]}},shifted[7:0]};
                    3'b001: rdata <= {{16{shifted[15]}},shifted[15:0]};
                    3'b100: rdata <= {24'b0,shifted[7:0]};
                    3'b101: rdata <= {16'b0,shifted[15:0]};
                    default: rdata <= response_data;
                endcase
                pending <= 0; completed <= 1;
                write_performed <= request_write;
            end
        end
    end
endmodule
