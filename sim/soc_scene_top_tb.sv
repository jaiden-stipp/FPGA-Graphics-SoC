`timescale 1ns/1ps
`include "renderer_types.svh"
`include "scene_stats.svh"
module soc_scene_top_tb;
    logic clk=0, rx_clk=0, tx_clk=0;
    always #10 clk=~clk;
    always #20 rx_clk=~rx_clk;
    always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0, tx_data, LEDG;
    logic rx_dv=0, rx_er=0, tx_en, tx_er, phy_ready;
    logic [1:0] KEY=0;
    logic [7:0] VGA_R,VGA_G,VGA_B;
    logic VGA_CLK,VGA_BLANK_N,VGA_SYNC_N,VGA_HS,VGA_VS;
    integer changed_frame=0, displayed=0;
    bit changed_view=0;
    model_matrix_3x4_t matrix;
    de2_115_soc_top #(.HEX_FILE("build/scene-test.hex"), .ENABLE_SDRAM(0)) dut (
        .CLOCK_50(clk), .KEY(KEY), .KEY3(1'b1),
        .ENET0_RX_CLK(rx_clk), .ENET0_TX_CLK(tx_clk), .ENET0_RX_DATA(rx_data),
        .ENET0_RX_DV(rx_dv), .ENET0_RX_ER(rx_er), .ENET0_TX_DATA(tx_data),
        .ENET0_TX_EN(tx_en), .ENET0_TX_ER(tx_er), .ENET0_RST_N(phy_ready), .LEDG(LEDG),
        .VGA_R(VGA_R), .VGA_G(VGA_G), .VGA_B(VGA_B), .VGA_CLK(VGA_CLK),
        .VGA_BLANK_N(VGA_BLANK_N), .VGA_SYNC_N(VGA_SYNC_N), .VGA_HS(VGA_HS), .VGA_VS(VGA_VS)
    );
    `include "control_packets.svh"
    always @(negedge clk) begin
        if (dut.soc.graphics.command_valid && dut.soc.graphics.command_ready) begin
            if (dut.soc.graphics.command_data.opcode==GFX_CMD_SET_VIEW_MATRIX) begin
                matrix=`GFX_VIEW_MATRIX(dut.soc.graphics.command_data);
                if (matrix.m02!=0) changed_view=1;
            end
            if (dut.soc.graphics.command_data.opcode==GFX_CMD_BEGIN_FRAME && changed_view && changed_frame==0)
                changed_frame=`GFX_ARGUMENT(dut.soc.graphics.command_data);
        end
    end
    initial begin
        repeat (5) @(posedge clk); #1; KEY=3;
        wait (phy_ready);
        repeat (20) @(posedge clk);
        send_control(1,2,0,0);
        if (dut.network_buttons!=2 || !dut.network_active) $fatal(1,"UDP did not reach board input");
        wait (changed_frame!=0);
        wait (dut.soc.scratch==changed_frame);
        if (dut.soc.error_flags || dut.network_error || tx_er ||
            dut.soc.memory.mmio.stats_snapshot[415 -: 32]!=`SCENE_EXPECTED_TRIANGLES ||
            dut.soc.memory.mmio.stats_snapshot[223 -: 32]==0)
            $fatal(1,"SM64 frame failed to render/display after UDP input");
        $display("PASS soc_scene_top_tb (UDP keyboard -> RV32I camera -> %0d GPU triangles -> VGA frame %0d)",
                 `SCENE_EXPECTED_TRIANGLES,changed_frame); $finish;
    end
    initial begin
        repeat (5000000) @(posedge clk);
        $fatal(1,"SM64 board timeout PC=%h scratch=%h",dut.soc.debug_pc,dut.soc.scratch);
    end
endmodule
