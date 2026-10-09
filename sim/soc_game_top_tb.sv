`timescale 1ns/1ps
module soc_game_top_tb;
    logic clk = 0, reset = 1;
    always #10 clk = ~clk;
    logic [7:0] buttons = 1;
    logic [31:0] debug_pc, scratch;
    logic frame_pending;
    logic [3:0] error_flags;
    logic [7:0] VGA_R, VGA_G, VGA_B;
    logic VGA_CLK, VGA_BLANK_N, VGA_SYNC_N, VGA_HS, VGA_VS;
    soc_top #(.HEX_FILE("build/game-test.hex")) dut (
        .sdram_reset(1'b0),.load_hold(1'b0),.load_valid(1'b0),.load_write(1'b0),
        .load_addr(32'b0),.load_wdata(32'b0),.load_ready(),.load_rdata(),.sdram_initialized(),.refresh_count(),
        .DRAM_CLK(),.DRAM_CKE(),.DRAM_CS_N(),.DRAM_RAS_N(),.DRAM_CAS_N(),.DRAM_WE_N(),
        .DRAM_ADDR(),.DRAM_BA(),.DRAM_DQM(),.DRAM_DQ(),.*);
    initial begin
        repeat (5) @(posedge clk); #1; reset = 0;
        for (integer i = 0; i < 3000000; i = i + 1) begin
            @(posedge clk); #1;
            if (error_flags != 0 || scratch == 32'hdead0001)
                $fatal(1, "Game SoC error=%h PC=%h", error_flags, debug_pc);
            if (scratch == 1) buttons = 2;
            if (scratch == 2) begin
                if (dut.memory.mmio.last_frame_id != 2 || frame_pending ||
                    dut.memory.mmio.stats_snapshot[415 -: 32] != 4 ||
                    dut.memory.mmio.stats_snapshot[223 -: 32] == 0)
                    $fatal(1, "Game did not render/present both meshes");
                $display("PASS soc_game_top_tb (%0d cycles, two game frames displayed)", i);
                $finish;
            end
        end
        $fatal(1, "Game SoC timeout PC=%h", debug_pc);
    end
endmodule
