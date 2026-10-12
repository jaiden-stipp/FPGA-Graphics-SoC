`timescale 1ns/1ps
module udp_loader_tb;
`ifdef SOC_GEOMETRY_WORKER
    localparam EXPECTED_CPU_FEATURES=32'h80000003;
`else
    localparam EXPECTED_CPU_FEATURES=32'h80000001;
`endif
    logic clk=0,rx_clk=0,tx_clk=0,reset=1;
    always #10 clk=~clk;always #20 rx_clk=~rx_clk;always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0,tx_data;
    logic rx_dv=0,rx_er=0,tx_en,tx_er,load_hold,load_valid,load_write,load_ready,initialized;
    logic [31:0] load_addr,load_wdata,load_rdata,scratch,refresh_count;
    logic [7:0] buttons;
    logic active,packet_seen,network_error;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR;wire [1:0] DRAM_BA;wire [3:0] DRAM_DQM;wire [31:0] DRAM_DQ;
    udp_controls #(.REQUIRE_LOAD(1)) controls (
        .clk(clk),.reset(reset),.rx_clk(rx_clk),.tx_clk(tx_clk),.rx_data(rx_data),.rx_dv(rx_dv),.rx_er(rx_er),
        .tx_data(tx_data),.tx_en(tx_en),.tx_er(tx_er),.buttons(buttons),.active(active),
        .packet_seen(packet_seen),.network_error(network_error),
        .load_hold(load_hold),.load_valid(load_valid),.load_write(load_write),.load_ready(load_ready),
        .load_addr(load_addr),.load_wdata(load_wdata),.load_rdata(load_rdata),
        .sdram_initialized(initialized),.scratch(scratch),.refresh_count(refresh_count)
    );
    soc_memory #(.HEX_FILE(""),.ENABLE_SDRAM(1)) memory (
        .clk(clk),.reset(reset||load_hold),.sdram_reset(reset),.pc(32'b0),.addr(32'b0),.wdata(32'b0),
        .funct3(3'b010),.read_en(1'b0),.write_en(1'b0),
        .load_hold(load_hold),.load_valid(load_valid),.load_write(load_write),.load_ready(load_ready),
        .load_addr(load_addr),.load_wdata(load_wdata),.load_rdata(load_rdata),
        .sdram_initialized(initialized),.scratch(scratch),.refresh_count(refresh_count),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(buttons),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);
    `include "control_packets.svh"
    `include "load_packets.svh"
    logic [415:0] response;
    integer reply_id=0,network_replies=0;
    always @(posedge clk) if(controls.reply_valid) begin
        reply_id=controls.reply_id;response=controls.reply_statistics;
    end
    // Check that a completion response crosses the TX CDC and goes out on MII.
    always @(posedge tx_clk) if(controls.ethernet.response_transmitter.frame_ready &&
        controls.ethernet.response_transmitter.frame_valid) network_replies=network_replies+1;
    task automatic check(input integer id,input [31:0] status);
        if(reply_id!=id || response[383:352]!=status || response[415:384]!=32'h53440100)
            $fatal(1,"Loader response %0d/%0d status %h/%h",reply_id,id,response[383:352],status);
    endtask
    initial begin
        repeat(5) @(posedge clk);#1;reset=0;wait(initialized);
        if(!load_hold) $fatal(1,"CPU started before package");
        send_control(0,0,0,0); // establish the return peer first
        send_load(1,1,0,0,0,0,0);check(1,0);
        send_load(2,2,3,32'h80000000,32'h01234567,32'h89abcdef,32'hfedcba98);check(2,0);
        send_load(3,3,3,32'h80000000,0,0,0);check(3,0);
        if(response[351:256]!={32'h01234567,32'h89abcdef,32'hfedcba98}) $fatal(1,"SDRAM readback");
        send_load(4,2,3,32'h80,32'habcdef01,32'h76543210,32'h55aa55aa);check(4,0);
        send_load(5,3,3,32'h80,0,0,0);check(5,0);
        if(response[351:256]!={32'habcdef01,32'h76543210,32'h55aa55aa}) $fatal(1,"CPU image readback");
        send_load(6,2,3,32'hfffc,1,2,3);check(6,1);
        send_load(7,2,1,32'h40000018,1,0,0);check(7,1);
        send_load(8,2,1,32'h80000001,1,0,0);check(8,1);
        send_load(9,2,3,32'h87fffffc,1,2,3);check(9,1);
        send_load(10,4,0,0,0,0,0);check(10,0);if(load_hold) $fatal(1,"CPU commit");
        send_load(11,2,1,32'h80,1,0,0);check(11,1);
        send_control(1,18,0,0);if(buttons!=18 || !active) $fatal(1,"Controls after load");
        send_load(12,5,0,0,0,0,0);check(12,0);
        if(response[95:0]!={32'h494e0101,EXPECTED_CPU_FEATURES,32'h00000003}) $fatal(1,"Loader feature advertisement");
        if(network_replies<12 || tx_er || memory.ram.mem[32]!=32'habcdef01) $fatal(1,"Loader TX/no-write guard");
        $display("PASS udp_loader_tb (MII/CRC/CDC, CPU and SDRAM readback, range/hold guards, keyboard preserved)");$finish;
    end
    initial begin #2000000;$fatal(1,"UDP loader timeout");end
endmodule
