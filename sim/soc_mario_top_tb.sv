`ifndef SOC_MARIO_TOP_TB
`define SOC_MARIO_TOP_TB
`timescale 1ns/1ps
`include "renderer_types.svh"
`include "game_stats.svh"
`include "mario-test_symbols.svh"
`define DISPLAY dut.soc.graphics.renderer.pipeline.display
module soc_mario_top_tb #(
    parameter HEX_FILE="build/mario-test.hex",
    parameter CAPTURE_STEM="build/mario",
    parameter TEST_NAME="soc_mario_top_tb",
    parameter ENABLE_SDRAM=0,
    parameter ASSET_FILE="build/mario-sdram.assets.hex",
    parameter PLAYER_ADDR=`MARIO_TEST_PLAYER_ADDR,
    parameter CLIP_ADDR=`MARIO_TEST_CLIP_ADDR,
    parameter ANIMATION_FRAME_ADDR=`MARIO_TEST_ANIMATION_FRAME_ADDR,
    parameter ANIMATION_CYCLES_ADDR=`MARIO_TEST_ANIMATION_CYCLES_ADDR,
    parameter UPLOAD_CYCLES_ADDR=`MARIO_TEST_UPLOAD_CYCLES_ADDR,
    parameter CPU_CYCLES_ADDR=`MARIO_TEST_CPU_CYCLES_ADDR
);
    logic clk=0,rx_clk=0,tx_clk=0;
    always #10 clk=~clk;
    always #20 rx_clk=~rx_clk;
    always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0,tx_data,LEDG;
    logic rx_dv=0,rx_er=0,tx_en,tx_er,phy_ready;
    logic [1:0] KEY=0;
    logic [7:0] VGA_R,VGA_G,VGA_B;
    logic VGA_CLK,VGA_BLANK_N,VGA_SYNC_N,VGA_HS,VGA_VS;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    integer current_frame=0,changed_frame=0;
    model_matrix_3x4_t matrix,first_model;
    model_matrix_3x4_t view;
    bit got_first=0;
    logic [7:0] pixels0[0:76799],pixels1[0:76799];
    logic [23:0] colors[0:255];
    de2_115_soc_top #(.HEX_FILE(HEX_FILE), .ENABLE_SDRAM(ENABLE_SDRAM)) dut (
        .CLOCK_50(clk),.KEY(KEY),.KEY3(1'b1),
        .ENET0_RX_CLK(rx_clk),.ENET0_TX_CLK(tx_clk),.ENET0_RX_DATA(rx_data),
        .ENET0_RX_DV(rx_dv),.ENET0_RX_ER(rx_er),.ENET0_TX_DATA(tx_data),
        .ENET0_TX_EN(tx_en),.ENET0_TX_ER(tx_er),.ENET0_RST_N(phy_ready),.LEDG(LEDG),
        .VGA_R(VGA_R),.VGA_G(VGA_G),.VGA_B(VGA_B),.VGA_CLK(VGA_CLK),
        .VGA_BLANK_N(VGA_BLANK_N),.VGA_SYNC_N(VGA_SYNC_N),.VGA_HS(VGA_HS),.VGA_VS(VGA_VS),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    `include "control_packets.svh"
    `include "load_packets.svh"
    generate if (ENABLE_SDRAM) begin : dram
        sdram_device_model chip(.*);
        initial begin : preload
            integer fd,word_index,read_count;
            reg [31:0] value;
            wait(dut.sdram_initialized);
            fd=$fopen(ASSET_FILE,"r"); if(!fd) $fatal(1,"Missing SDRAM fixture");
            word_index=0;
            while(!$feof(fd)) begin
                read_count=$fscanf(fd,"%h\n",value);
                if(read_count==1) begin chip.memory[word_index]=value; word_index=word_index+1; end
            end
            $fclose(fd);
        end
    end endgenerate
    // Observe the real post-depth-test RAM write ports. This is a GPU frame
    // capture, not a software approximation of the renderer.
    always @(negedge clk) begin
        if (`DISPLAY.framebuffer0.ram_write_enable)
            pixels0[`DISPLAY.framebuffer0.ram_write_address]=`DISPLAY.framebuffer0.ram_write_data;
        if (`DISPLAY.framebuffer1.ram_write_enable)
            pixels1[`DISPLAY.framebuffer1.ram_write_address]=`DISPLAY.framebuffer1.ram_write_data;
        if (`DISPLAY.palette_write) colors[`DISPLAY.palette_address]=`DISPLAY.palette_write_rgb;
        if (dut.soc.graphics.command_valid && dut.soc.graphics.command_ready) begin
            if (dut.soc.graphics.command_data.opcode==GFX_CMD_SET_VIEW_MATRIX)
                view=`GFX_VIEW_MATRIX(dut.soc.graphics.command_data);
            if (dut.soc.graphics.command_data.opcode==GFX_CMD_BEGIN_FRAME)
                current_frame=`GFX_ARGUMENT(dut.soc.graphics.command_data);
            if (dut.soc.graphics.command_data.opcode==GFX_CMD_DRAW_MESH &&
                `GFX_DRAW_MESH_HANDLE(dut.soc.graphics.command_data)==`MARIO_WORLD_MESHES) begin
                matrix=`GFX_MODEL_MATRIX(dut.soc.graphics.command_data);
                if (!got_first) begin first_model=matrix; got_first=1; end
                if (matrix.m03>first_model.m03 && matrix.m13>first_model.m13 && changed_frame==0)
                    changed_frame=current_frame;
            end
        end
    end
    task automatic capture(input string path);
        integer fd,actor_pixels,meta;
        logic [7:0] index;
        logic [23:0] rgb;
        renderer_stats_t stats;
        begin
            fd=$fopen(path,"w");
            if (!fd) $fatal(1,"Cannot write frame capture");
            $fdisplay(fd,"P3\n320 240\n255");
            actor_pixels=0;
            for (integer i=0;i<76800;i=i+1) begin
                index=`DISPLAY.front_page_pixel ? pixels1[i] : pixels0[i];
                rgb=colors[index];
                if (rgb[23:16]>80 && rgb[15:8]<30 && rgb[7:0]<30) actor_pixels=actor_pixels+1;
                $fdisplay(fd,"%0d %0d %0d",rgb[23:16],rgb[15:8],rgb[7:0]);
            end
            $fclose(fd);
            if (actor_pixels<20) $fatal(1,"Mario red geometry not visible (%0d pixels)",actor_pixels);
            stats=dut.soc.memory.mmio.stats_snapshot;
            meta=$fopen({path,".json"},"w");
            if (!meta) $fatal(1,"Cannot write GPU performance capture");
            $fdisplay(meta,"{\"triangles\":%0d,\"total_cycles\":%0d,\"swap_wait_cycles\":%0d,\"geometry_cycles\":%0d,\"geometry_stall_cycles\":%0d,\"raster_cycles\":%0d,\"clear_cycles\":%0d,\"bounding_box_pixels\":%0d,\"depth_rejected\":%0d,",
                      stats.triangles_submitted,stats.total_cycles,stats.swap_wait_cycles,
                      stats.geometry_cycles,stats.geometry_stall_cycles,stats.raster_cycles,
                      stats.clear_cycles,stats.bounding_box_pixels,stats.depth_rejected);
            $fdisplay(meta,"\"view\":[%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d],\"focal\":%0d,\"near_z\":%0d,",
                      $signed(view.m00),$signed(view.m01),$signed(view.m02),$signed(view.m03),
                      $signed(view.m10),$signed(view.m11),$signed(view.m12),$signed(view.m13),
                      $signed(view.m20),$signed(view.m21),$signed(view.m22),$signed(view.m23),
                      `MARIO_CAMERA_FOCAL,`MARIO_CAMERA_NEAR);
            $fdisplay(meta,"\"model\":[%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d],",
                      $signed(matrix.m00),$signed(matrix.m01),$signed(matrix.m02),$signed(matrix.m03),
                      $signed(matrix.m10),$signed(matrix.m11),$signed(matrix.m12),$signed(matrix.m13),
                      $signed(matrix.m20),$signed(matrix.m21),$signed(matrix.m22),$signed(matrix.m23));
            $fdisplay(meta,"\"animation\":%0d,\"animation_frame\":%0d,\"grounded\":%0d,\"animation_cycles\":%0d,\"upload_cycles\":%0d,\"cpu_cycles\":%0d}",
                      dut.soc.memory.ram.mem[CLIP_ADDR>>2],dut.soc.memory.ram.mem[ANIMATION_FRAME_ADDR>>2],
                      dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+4],dut.soc.memory.ram.mem[ANIMATION_CYCLES_ADDR>>2],
                      dut.soc.memory.ram.mem[UPLOAD_CYCLES_ADDR>>2],dut.soc.memory.ram.mem[CPU_CYCLES_ADDR>>2]);
            $fclose(meta);
            if (stats.total_cycles-stats.swap_wait_cycles>1666667)
                $fatal(1,"GPU active work exceeds the 30 Hz budget");
            if (dut.soc.memory.ram.mem[CPU_CYCLES_ADDR>>2]+stats.total_cycles-stats.swap_wait_cycles>1666667)
                $fatal(1,"CPU work + GPU active work exceeds the 30 Hz budget");
            $display("Captured %s (%0d visible Mario red pixels)",path,actor_pixels);
        end
    endtask
    initial begin
        repeat (5) @(posedge clk); #1; KEY=3;
        wait (phy_ready);
        if(ENABLE_SDRAM) begin
            send_control(0,0,0,0);
            send_load(123,4,0,0,0,0,0);
            if(dut.load_hold) $fatal(1,"SDRAM package commit failed");
        end
        wait (dut.soc.scratch!=0);
        if (dut.soc.scratch[31:16]==16'hdead) $fatal(1,"Mario firmware failed before capture");
        capture({CAPTURE_STEM,"-standing.ppm"});
        send_control(1,18,0,0);
        if (dut.network_buttons!=18 || !dut.network_active) $fatal(1,"UDP jump/move input failed");
        wait (changed_frame!=0);
        wait (dut.soc.scratch==changed_frame);
        if (dut.soc.error_flags || dut.network_error || tx_er ||
            dut.soc.memory.mmio.stats_snapshot[415 -: 32]!=`MARIO_EXPECTED_TRIANGLES ||
            dut.soc.memory.mmio.stats_snapshot[223 -: 32]==0)
            $fatal(1,"Mario GPU/VGA frame failed after UDP input");
        capture({CAPTURE_STEM,"-jumping.ppm"});
        $display("PASS %s (UDP controls -> RV32I move/jump -> %0d GPU triangles -> VGA frame %0d)",
                 TEST_NAME,`MARIO_EXPECTED_TRIANGLES,changed_frame); $finish;
    end
    initial begin
        repeat (ENABLE_SDRAM ? 25000000 : 12000000) @(posedge clk);
        $fatal(1,"Mario board timeout PC=%h scratch=%h",dut.soc.debug_pc,dut.soc.scratch);
    end
endmodule
`undef DISPLAY
`endif
