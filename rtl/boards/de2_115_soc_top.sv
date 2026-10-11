module de2_115_soc_top #(
    parameter HEX_FILE = "build/firmware.hex",
    parameter MIF_FILE = "build/firmware.mif",
    parameter integer INPUT_TIMEOUT_CYCLES = 15000000,
    parameter ENABLE_SDRAM = 0,
    parameter ENABLE_CACHE = 1,
    parameter ENABLE_BURST = 1,
    parameter CACHE_LINE_BYTES = 32
)(
    input logic CLOCK_50,
    input logic [1:0] KEY,
    input logic KEY3,
    input logic ENET0_RX_CLK, ENET0_TX_CLK,
    input logic [3:0] ENET0_RX_DATA,
    input logic ENET0_RX_DV, ENET0_RX_ER,
    output logic [3:0] ENET0_TX_DATA,
    output logic ENET0_TX_EN, ENET0_TX_ER, ENET0_RST_N,
    output logic [3:0] LEDG,
    output logic [7:0] VGA_R, VGA_G, VGA_B,
    output logic VGA_CLK, VGA_BLANK_N, VGA_SYNC_N, VGA_HS, VGA_VS,
    output wire DRAM_CLK,
    output wire DRAM_CKE, DRAM_CS_N, DRAM_RAS_N, DRAM_CAS_N, DRAM_WE_N,
    output wire [12:0] DRAM_ADDR,
    output wire [1:0] DRAM_BA,
    output wire [3:0] DRAM_DQM,
    inout wire [31:0] DRAM_DQ
);
    logic [1:0] reset_sync;
    logic frame_pending;
    logic [3:0] errors;
    logic [7:0] network_buttons;
    logic [23:0] network_look;
    logic network_active, packet_seen, network_error;
    logic load_hold, load_valid, load_write, load_ready, sdram_initialized;
    logic [31:0] load_addr, load_wdata, load_rdata, scratch, refresh_count;
    logic [19:0] phy_reset_counter;
    always_ff @(posedge CLOCK_50 or negedge KEY[0]) begin
        if (!KEY[0]) reset_sync <= 0;
        else reset_sync <= {reset_sync[0], 1'b1};
    end
    always_ff @(posedge CLOCK_50 or negedge KEY[0]) begin
        if (!KEY[0]) phy_reset_counter <= 0;
        else if (!(&phy_reset_counter)) phy_reset_counter <= phy_reset_counter + 1'b1;
    end
    assign ENET0_RST_N = &phy_reset_counter;
`ifdef SOC_DISABLE_COMMAND_DMA
    localparam GPU_FEATURES=3;
`else
    localparam GPU_FEATURES=(ENABLE_SDRAM && ENABLE_CACHE && ENABLE_BURST && CACHE_LINE_BYTES==32)?7:3;
`endif
    udp_controls #(.TIMEOUT_CYCLES(INPUT_TIMEOUT_CYCLES), .REQUIRE_LOAD(ENABLE_SDRAM),.GPU_FEATURES(GPU_FEATURES)) controls (
        .clk(CLOCK_50), .reset(!reset_sync[1] || !ENET0_RST_N),
        .rx_clk(ENET0_RX_CLK), .tx_clk(ENET0_TX_CLK),
        .rx_data(ENET0_RX_DATA), .rx_dv(ENET0_RX_DV), .rx_er(ENET0_RX_ER),
        .tx_data(ENET0_TX_DATA), .tx_en(ENET0_TX_EN), .tx_er(ENET0_TX_ER),
        .buttons(network_buttons), .look_state(network_look), .active(network_active), .packet_seen(packet_seen),
        .network_error(network_error), .load_hold(load_hold), .load_valid(load_valid),
        .load_write(load_write), .load_addr(load_addr), .load_wdata(load_wdata),
        .load_ready(load_ready), .load_rdata(load_rdata), .sdram_initialized(sdram_initialized),
        .scratch(scratch), .refresh_count(refresh_count)
    );
    soc_top #(.HEX_FILE(HEX_FILE), .MIF_FILE(MIF_FILE), .ENABLE_SDRAM(ENABLE_SDRAM), .ENABLE_CACHE(ENABLE_CACHE), .ENABLE_BURST(ENABLE_BURST), .CACHE_LINE_BYTES(CACHE_LINE_BYTES)) soc (
        .clk(CLOCK_50), .reset(!reset_sync[1]),
        .buttons(network_buttons | {6'b0, !KEY3, !KEY[1]}),
        .look_state(network_look),
        .debug_pc(), .scratch(scratch), .frame_pending(frame_pending), .error_flags(errors),
        .sdram_reset(!reset_sync[1]), .load_hold(load_hold), .load_valid(load_valid),
        .load_write(load_write), .load_addr(load_addr), .load_wdata(load_wdata),
        .load_ready(load_ready), .load_rdata(load_rdata), .sdram_initialized(sdram_initialized),
        .refresh_count(refresh_count),
        .DRAM_CLK(DRAM_CLK), .DRAM_CKE(DRAM_CKE), .DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N), .DRAM_CAS_N(DRAM_CAS_N), .DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR), .DRAM_BA(DRAM_BA), .DRAM_DQM(DRAM_DQM), .DRAM_DQ(DRAM_DQ),
        .VGA_R(VGA_R), .VGA_G(VGA_G), .VGA_B(VGA_B), .VGA_CLK(VGA_CLK),
        .VGA_BLANK_N(VGA_BLANK_N), .VGA_SYNC_N(VGA_SYNC_N),
        .VGA_HS(VGA_HS), .VGA_VS(VGA_VS)
    );
    assign LEDG = {((|errors) || network_error), network_active, frame_pending, reset_sync[1]};
endmodule
