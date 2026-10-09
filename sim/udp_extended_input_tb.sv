`timescale 1ns/1ps
module udp_extended_input_tb;
    logic clk=0,rx_clk=0,tx_clk=0,reset=1;
    always #10 clk=~clk;always #20 rx_clk=~rx_clk;always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0,tx_data;logic rx_dv=0,rx_er=0,tx_en,tx_er;
    logic [7:0] buttons;logic [23:0] look_state;
    logic active,packet_seen,network_error;
    udp_controls #(.TIMEOUT_CYCLES(10000)) dut(
        .load_hold(),.load_valid(),.load_write(),.load_addr(),.load_wdata(),
        .load_ready(1'b0),.sdram_initialized(1'b0),.load_rdata(32'b0),.scratch(32'b0),.refresh_count(32'b0),.*);
    `include "control_packets.svh"
    `include "input_packets.svh"
    initial begin
        repeat(5)@(posedge clk);#1;reset=0;
        send_input(254,8'hf4,128,240,0);
        if(buttons!=8'hf4 || look_state!=24'h80f080 || !active || network_error)$fatal(1,"Extended input decode");
        send_input(254,0,2,0,0);
        if(buttons!=8'hf4 || look_state!=24'h80f080)$fatal(1,"Duplicate reapplied angles");
        send_input(253,0,2,0,0);
        if(look_state!=24'h80f080)$fatal(1,"Stale input accepted");
        send_input(255,0,255,32,0);send_input(0,16,0,224,0);
        if(buttons!=16 || look_state!=24'h80e000)$fatal(1,"Wrap/extreme pitch");
        send_input(1,0,44,0,1);
        if(buttons!=16 || look_state!=24'h80e000 || !network_error)$fatal(1,"Bad CRC changed input");
        send_input(2,0,45,33,0);
        if(buttons!=16 || look_state!=24'h80e000)$fatal(1,"Invalid pitch accepted");
        send_input(3,64,7,0,0);
        if(buttons!=64 || look_state!=24'h800007)$fatal(1,"Valid packet recovery");
        repeat(10100)@(posedge clk);#1;
        if(buttons || look_state || active)$fatal(1,"Deadman failed");
        send_control(100,4,0,0);
        if(buttons!=4 || look_state)$fatal(1,"Legacy keyboard compatibility");
        $display("PASS udp_extended_input_tb (real MII CRC, absolute angles, buttons, sequence, pitch bounds, deadman, legacy)");$finish;
    end
    initial begin #2000000;$fatal(1,"Input timeout");end
endmodule
