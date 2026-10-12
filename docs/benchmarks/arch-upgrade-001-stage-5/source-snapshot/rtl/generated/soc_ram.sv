import pipeline_pkg::*;

// Unified instruction/data memory.
//
// Quartus synthesis uses a native Cyclone IV altsyncram in true dual-port
// mode. The RAM runs on the falling edge so its synchronous reads settle
// before the pipeline captures them on the next rising edge. Simulation keeps
// an ordinary array because the testbenches load and inspect it directly.
module soc_ram #(
    parameter integer N = 16834,
    parameter INIT_FILE = "5-Stage-Pipeline/memory/program.mif",
    parameter HEX_FILE = "build/firmware.hex",
    parameter DEVICE_FAMILY = "Cyclone IV E"
)(
    input logic clk,
    input logic [31:0] pc, d_addr, d_wdata,
    input logic [2:0] d_funct3,
    input logic dw_en, dr_en,
    output logic [31:0] Instruction, d_rdata,
    output logic misaligned,
    output logic write_performed
);
    localparam integer ADDRESS_WIDTH = $clog2(N);

    logic [31:0] d_word;
    logic [1:0] byte_offset;
    logic [3:0] d_byteena;
    logic [31:0] d_ram_wdata;
    logic instruction_address_valid;
    logic data_address_valid;

    always_comb begin
        byte_offset = d_addr[1:0];
        instruction_address_valid = (pc[31:2] < N);
        data_address_valid = (d_addr[31:2] < N);

        misaligned = 1'b0;
        if (dr_en || dw_en) begin
            case (d_funct3)
                HALF, HALFU: misaligned = d_addr[0];
                WORD:        misaligned = |d_addr[1:0];
                default:     misaligned = 1'b0;
            endcase
        end

        write_performed = dw_en && !misaligned && data_address_valid;

        // altsyncram byte enables select lanes from the same positions in the
        // write-data bus, so subword stores are shifted into the addressed lane.
        d_byteena = 4'b0000;
        d_ram_wdata = d_wdata;
        case (d_funct3)
            BYTE: begin
                d_byteena = 4'b0001 << byte_offset;
                d_ram_wdata = d_wdata << (byte_offset * 8);
            end
            HALF: begin
                d_byteena = byte_offset[1] ? 4'b1100 : 4'b0011;
                d_ram_wdata = byte_offset[1] ? (d_wdata << 16) : d_wdata;
            end
            WORD: d_byteena = 4'b1111;
            default: d_byteena = 4'b0000;
        endcase
    end

`ifdef ALTERA_RESERVED_QIS
    logic [31:0] instruction_word;
    logic [31:0] data_word;

    // Native Quartus memory IP. Both addresses, write data, and byte enables
    // are captured on the falling edge through the inverted clock. Outputs are
    // left unregistered so they are available at the next pipeline rising edge.
    altsyncram #(
        .address_reg_b("CLOCK0"),
        .byteena_reg_b("CLOCK0"),
        .clock_enable_input_a("BYPASS"),
        .clock_enable_input_b("BYPASS"),
        .clock_enable_output_a("BYPASS"),
        .clock_enable_output_b("BYPASS"),
        .indata_reg_b("CLOCK0"),
        .init_file(INIT_FILE),
        .intended_device_family(DEVICE_FAMILY),
        .lpm_type("altsyncram"),
        .numwords_a(N),
        .numwords_b(N),
        .operation_mode("BIDIR_DUAL_PORT"),
        .outdata_aclr_a("NONE"),
        .outdata_aclr_b("NONE"),
        .outdata_reg_a("UNREGISTERED"),
        .outdata_reg_b("UNREGISTERED"),
        .power_up_uninitialized("FALSE"),
        .read_during_write_mode_mixed_ports("DONT_CARE"),
        .read_during_write_mode_port_b("NEW_DATA_NO_NBE_READ"),
        .widthad_a(ADDRESS_WIDTH),
        .widthad_b(ADDRESS_WIDTH),
        .width_a(32),
        .width_b(32),
        .width_byteena_a(1),
        .width_byteena_b(4),
        .wrcontrol_wraddress_reg_b("CLOCK0")
    ) ram_ip (
        .address_a(pc[ADDRESS_WIDTH+1:2]),
        .address_b(d_addr[ADDRESS_WIDTH+1:2]),
        .byteena_a(1'b1),
        .byteena_b(d_byteena),
        .clock0(~clk),
        .data_a(32'b0),
        .data_b(d_ram_wdata),
        .q_a(instruction_word),
        .q_b(data_word),
        .wren_a(1'b0),
        .wren_b(write_performed)
    );

    always_comb begin
        Instruction = instruction_address_valid
                    ? instruction_word : 32'h00000013;
        d_word = data_address_valid ? data_word : 32'b0;
    end
`else
    logic [31:0] mem [0:N-1];
    initial begin
        for (integer i = 0; i < N; i = i + 1) mem[i] = 0;
        if (HEX_FILE != "") $readmemh(HEX_FILE, mem);
    end

    // Fast behavioral model used by ModelSim and Icarus. Writes happen on the
    // falling edge to match the architectural timing of the Quartus RAM path.
    always_comb begin
        Instruction = instruction_address_valid
                    ? mem[pc[ADDRESS_WIDTH+1:2]] : 32'h00000013;
        d_word = data_address_valid
               ? mem[d_addr[ADDRESS_WIDTH+1:2]] : 32'b0;
    end

    always @(negedge clk) begin
        if (write_performed) begin
            case (d_funct3)
                BYTE: begin
                    case (byte_offset)
                        2'd0: mem[d_addr[ADDRESS_WIDTH+1:2]][7:0]   <= d_wdata[7:0];
                        2'd1: mem[d_addr[ADDRESS_WIDTH+1:2]][15:8]  <= d_wdata[7:0];
                        2'd2: mem[d_addr[ADDRESS_WIDTH+1:2]][23:16] <= d_wdata[7:0];
                        2'd3: mem[d_addr[ADDRESS_WIDTH+1:2]][31:24] <= d_wdata[7:0];
                    endcase
                end
                HALF: begin
                    if (byte_offset[1])
                        mem[d_addr[ADDRESS_WIDTH+1:2]][31:16] <= d_wdata[15:0];
                    else
                        mem[d_addr[ADDRESS_WIDTH+1:2]][15:0] <= d_wdata[15:0];
                end
                WORD: mem[d_addr[ADDRESS_WIDTH+1:2]] <= d_wdata;
                default: begin end
            endcase
        end
    end
`endif

    always_comb begin
        d_rdata = 32'b0;

        if (dr_en && !misaligned && data_address_valid) begin
            case (d_funct3)
                BYTE: begin
                    case (byte_offset)
                        2'd0: d_rdata = {{24{d_word[7]}},  d_word[7:0]};
                        2'd1: d_rdata = {{24{d_word[15]}}, d_word[15:8]};
                        2'd2: d_rdata = {{24{d_word[23]}}, d_word[23:16]};
                        2'd3: d_rdata = {{24{d_word[31]}}, d_word[31:24]};
                    endcase
                end
                HALF: begin
                    if (byte_offset[1])
                        d_rdata = {{16{d_word[31]}}, d_word[31:16]};
                    else
                        d_rdata = {{16{d_word[15]}}, d_word[15:0]};
                end
                WORD: d_rdata = d_word;
                BYTEU: begin
                    case (byte_offset)
                        2'd0: d_rdata = {24'b0, d_word[7:0]};
                        2'd1: d_rdata = {24'b0, d_word[15:8]};
                        2'd2: d_rdata = {24'b0, d_word[23:16]};
                        2'd3: d_rdata = {24'b0, d_word[31:24]};
                    endcase
                end
                HALFU: begin
                    if (byte_offset[1])
                        d_rdata = {16'b0, d_word[31:16]};
                    else
                        d_rdata = {16'b0, d_word[15:0]};
                end
                default: d_rdata = 32'b0;
            endcase
        end
    end
endmodule
