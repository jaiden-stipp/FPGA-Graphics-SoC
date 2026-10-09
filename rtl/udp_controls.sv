`include "renderer_types.svh"
// Reuse the existing GP/GF UDP transport, ARP replies and asynchronous FIFOs.
// A reserved palette-shaped envelope is consumed here as input, never sent to GPU.
module udp_controls #(
    parameter integer TIMEOUT_CYCLES = 15000000,
    parameter REQUIRE_LOAD = 0
)(
    input logic clk, reset,
    input logic rx_clk, tx_clk,
    input logic [3:0] rx_data,
    input logic rx_dv, rx_er,
    output logic [3:0] tx_data,
    output logic tx_en, tx_er,
    output logic [7:0] buttons,
    output logic [23:0] look_state,
    output logic active, packet_seen, network_error,
    output logic load_hold, load_valid, load_write,
    output logic [31:0] load_addr, load_wdata,
    input tri0 load_ready, sdram_initialized,
    input tri0 [31:0] load_rdata, scratch, refresh_count
);
    graphics_command_t command_data;
    logic command_valid, decoder_error, overflow;
    logic [31:0] argument;
    logic [7:0] last_sequence, delta;
    logic have_sequence, envelope, key_envelope, input_envelope;
    logic [7:0] incoming_sequence;
    logic load_envelope, load_error, command_ready, reply_valid;
    logic [31:0] reply_id;
    logic [415:0] reply_statistics;
    udp_memory_loader #(.REQUIRE_LOAD(REQUIRE_LOAD)) loader (
        .clk(clk), .reset(reset), .command_data(command_data), .command_valid(command_valid),
        .command_ready(command_ready), .envelope(load_envelope), .error(load_error), .hold_cpu(load_hold),
        .bus_valid(load_valid), .bus_write(load_write), .bus_addr(load_addr), .bus_wdata(load_wdata),
        .bus_ready(load_ready), .bus_rdata(load_rdata), .initialized(sdram_initialized),
        .scratch(scratch), .refresh_count(refresh_count), .reply_valid(reply_valid),
        .reply_id(reply_id), .reply_statistics(reply_statistics)
    );
    logic [$clog2(TIMEOUT_CYCLES+1)-1:0] age;
    assign argument = `GFX_ARGUMENT(command_data);
    assign incoming_sequence = input_envelope ? command_data.payload[167:160] : argument[15:8];
    assign delta = incoming_sequence - last_sequence;
    assign key_envelope = command_data.opcode == GFX_CMD_SET_PALETTE &&
                      argument[31:16] == 16'hff4b && argument[7:5] == 0;
    // IN v1: sequence, buttons, absolute yaw, signed pitch, 17 reserved zeros.
    // Absolute angles survive packet loss and never repeat a mouse delta.
    assign input_envelope = command_data.opcode == GFX_CMD_SET_VIEW_MATRIX &&
        command_data.payload[191:168] == 24'h494e01 &&
        command_data.payload[135:0] == 0 &&
        (command_data.payload[143:136] <= 32 || command_data.payload[143:136] >= 224);
    assign envelope = key_envelope || input_envelope;
    ethernet_command_receiver ethernet (
        .system_clk(clk), .reset(reset), .mii_rx_clk(rx_clk),
        .mii_rx_data(rx_data), .mii_rx_dv(rx_dv), .mii_rx_er(rx_er),
        .mii_tx_clk(tx_clk), .mii_tx_data(tx_data), .mii_tx_en(tx_en), .mii_tx_er(tx_er),
        .command_data(command_data), .command_valid(command_valid), .command_ready(command_ready),
        .command_error(command_valid && command_ready && !envelope && !load_envelope), .frame_done(reply_valid),
        .frame_done_id(reply_id), .frame_statistics(reply_statistics),
        .decoder_error(decoder_error), .receive_overflow(overflow), .packet_seen(packet_seen)
    );
    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            buttons <= 0; look_state <= 0; active <= 0; have_sequence <= 0;
            age <= 0; last_sequence <= 0; network_error <= 0;
        end else begin
            if (decoder_error || overflow || load_error || (command_valid && command_ready && !envelope && !load_envelope)) network_error <= 1;
            if (active) begin
                if (age == TIMEOUT_CYCLES-1) begin
                    buttons <= 0; look_state <= 0; active <= 0; have_sequence <= 0;
                end else age <= age + 1'b1;
            end
            // Reject duplicates/reordering with modular sequence comparison.
            if (command_valid && command_ready && envelope && (!have_sequence || (delta != 0 && !delta[7]))) begin
                buttons <= input_envelope ? command_data.payload[159:152] : argument[7:0];
                look_state <= input_envelope ? {8'h80,command_data.payload[143:136],command_data.payload[151:144]} : 24'b0;
                last_sequence <= incoming_sequence;
                have_sequence <= 1; active <= 1; age <= 0;
            end
        end
    end
endmodule
