// One synchronous read, one write. Parity banks retain original RAM latency.
module pixel_bank_ram #(parameter int WORDS=38400, ADDR_BITS=$clog2(WORDS))(
    input logic write_clk,read_clk,
    input logic [ADDR_BITS-1:0] write_address,read_address,
    input logic [7:0] write_data,
    input logic write_enable,read_enable,
    output wire [7:0] read_data
);
    altsyncram #(.operation_mode("DUAL_PORT"),.width_a(8),.width_b(8),
        .widthad_a(ADDR_BITS),.widthad_b(ADDR_BITS),.numwords_a(WORDS),.numwords_b(WORDS),
        .address_reg_b("CLOCK1"),.rdcontrol_reg_b("CLOCK1"),.outdata_reg_b("UNREGISTERED"),
        .ram_block_type("M9K"),.intended_device_family("Cyclone IV E"),
        .power_up_uninitialized("FALSE"),.read_during_write_mode_mixed_ports("DONT_CARE"),
        .lpm_type("altsyncram")) ram(
        .address_a(write_address),.address_b(read_address),.clock0(write_clk),.clock1(read_clk),
        .clocken0(1'b1),.clocken1(1'b1),.data_a(write_data),
        .rden_b(read_enable),.wren_a(write_enable),.q_b(read_data));
endmodule
