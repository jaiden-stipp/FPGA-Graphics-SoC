`timescale 1ns/1ps
module udp_controls_tb;
    logic clk=0, rx_clk=0, tx_clk=0, reset=1;
    always #10 clk=~clk;
    always #20 rx_clk=~rx_clk;
    always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0, tx_data;
    logic rx_dv=0, rx_er=0, tx_en, tx_er;
    logic [7:0] buttons;
    logic [23:0] look_state;
    logic active, packet_seen, network_error;
    udp_controls #(.TIMEOUT_CYCLES(10000)) dut (
        .load_hold(),.load_valid(),.load_write(),.load_addr(),.load_wdata(),
        .load_ready(1'b0),.sdram_initialized(1'b0),.load_rdata(32'b0),.scratch(32'b0),.refresh_count(32'b0),.*);
    `include "control_packets.svh"
    initial begin
        repeat (5) @(posedge clk); #1; reset=0;
        send_control(254, 1, 0, 0);
        if (buttons!=1 || !active || !packet_seen || network_error) $fatal(1,"UDP key-down");
        send_control(255, 6, 0, 0);
        if (buttons!=6) $fatal(1,"Multiple UDP keys");
        send_control(255, 0, 0, 0);
        if (buttons!=6) $fatal(1,"Duplicate state was applied");
        send_control(253, 0, 0, 0);
        if (buttons!=6) $fatal(1,"Stale state was applied");
        send_control(0, 0, 0, 0);
        if (buttons!=0 || !active) $fatal(1,"Sequence wrap/key release");
        send_control(1, 16, 0, 1);
        if (buttons!=0) $fatal(1,"Wrong UDP port accepted");
        send_control(2, 16, 1, 0);
        if (buttons!=0 || !network_error) $fatal(1,"Bad command CRC accepted");
        send_control(3, 16, 0, 0);
        if (buttons!=16) $fatal(1,"CRC error recovery");
        repeat (10100) @(posedge clk); #1;
        if (buttons!=0 || active) $fatal(1,"Lost connection left keys down");
        send_control(200, 8, 0, 0);
        if (buttons!=8 || !active || tx_er) $fatal(1,"Sender restart");
        $display("PASS udp_controls_tb (MII/UDP/CDC/CRC/sequence/release/deadman)"); $finish;
    end
    initial begin #2000000; $fatal(1,"UDP test timeout"); end
endmodule
