`timescale 1ns/1ps
`include "renderer_types.svh"
`include "quake-sdram-test_symbols.svh"
`define QDISPLAY dut.soc.graphics.renderer.pipeline.display
module quake_sdram_top_tb #(
    parameter HEX_FILE="build/quake-sdram-test.hex",
    parameter ASSET_FILE="build/quake-sdram.assets.hex",
    parameter CAPTURE_PREFIX="quake-sdram",
    parameter TEST_NAME="quake_sdram_top_tb",
    parameter PLAYER_ADDR=`QUAKE_SDRAM_TEST_PLAYER_ADDR,
    parameter CPU_CYCLES_ADDR=`QUAKE_SDRAM_TEST_CPU_CYCLES_ADDR,
    parameter EXPECTED_TRIANGLES=786,
    parameter INTERACTIVE=0,
    parameter DEMO_STATE_ADDR=0,
    parameter FRAME_CYCLES_ADDR=0,
    parameter MIN_WORLD_PIXELS=20000,
    parameter STANDING_ONLY=0,
    parameter ENFORCE_BUDGET=1
);
    logic clk=0,rx_clk=0,tx_clk=0;
    always #10 clk=~clk; always #20 rx_clk=~rx_clk; always #19 tx_clk=~tx_clk;
    logic [3:0] rx_data=0,tx_data,LEDG;
    logic rx_dv=0,rx_er=0,tx_en,tx_er,phy_ready;
    logic [1:0] KEY=0;
    logic [7:0] VGA_R,VGA_G,VGA_B;
    logic VGA_CLK,VGA_BLANK_N,VGA_SYNC_N,VGA_HS,VGA_VS;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    logic [7:0] pixels0[0:76799],pixels1[0:76799]; logic [23:0] colors[0:255];
    model_matrix_3x4_t view,first_view;
    integer current_frame=0,changed_frame=0,standing_y=0; bit got_view=0,in_frame=0;
    de2_115_soc_top #(.HEX_FILE(HEX_FILE),.ENABLE_SDRAM(1)) dut (
        .CLOCK_50(clk),.KEY(KEY),.KEY3(1'b1),.ENET0_RX_CLK(rx_clk),.ENET0_TX_CLK(tx_clk),
        .ENET0_RX_DATA(rx_data),.ENET0_RX_DV(rx_dv),.ENET0_RX_ER(rx_er),
        .ENET0_TX_DATA(tx_data),.ENET0_TX_EN(tx_en),.ENET0_TX_ER(tx_er),.ENET0_RST_N(phy_ready),.LEDG(LEDG),
        .VGA_R(VGA_R),.VGA_G(VGA_G),.VGA_B(VGA_B),.VGA_CLK(VGA_CLK),
        .VGA_BLANK_N(VGA_BLANK_N),.VGA_SYNC_N(VGA_SYNC_N),.VGA_HS(VGA_HS),.VGA_VS(VGA_VS),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),
        .DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),.DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),
        .DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);
    `include "control_packets.svh"
    `include "input_packets.svh"
    `include "load_packets.svh"
    initial begin : preload
        integer fd,index,read_count; reg [31:0] value;
        wait(dut.sdram_initialized);
        fd=$fopen(ASSET_FILE,"r"); if(!fd) $fatal(1,"Missing scene assets");
        index=0;
        while(!$feof(fd)) begin
            read_count=$fscanf(fd,"%h\n",value);
            if(read_count==1) begin chip.write_word(index,value); index=index+1; end
        end
        $fclose(fd);
    end
    always @(negedge clk) begin
        if (`QDISPLAY.framebuffer0.ram_write_enable)
            pixels0[`QDISPLAY.framebuffer0.ram_write_address]=`QDISPLAY.framebuffer0.ram_write_data;
        if (`QDISPLAY.framebuffer1.ram_write_enable)
            pixels1[`QDISPLAY.framebuffer1.ram_write_address]=`QDISPLAY.framebuffer1.ram_write_data;
        if (`QDISPLAY.palette_write) colors[`QDISPLAY.palette_address]=`QDISPLAY.palette_write_rgb;
        if(dut.soc.graphics.command_valid && dut.soc.graphics.command_ready) begin
            if(dut.soc.graphics.command_data.opcode==GFX_CMD_SET_VIEW_MATRIX && !in_frame) begin
                view=`GFX_VIEW_MATRIX(dut.soc.graphics.command_data);
                if(!got_view) begin first_view=view; got_view=1; end
            end
            if(dut.soc.graphics.command_data.opcode==GFX_CMD_BEGIN_FRAME) begin
                in_frame=1;
                current_frame=`GFX_ARGUMENT(dut.soc.graphics.command_data);
                if(view.m02!=first_view.m02 && !changed_frame) changed_frame=current_frame;
            end
            if(dut.soc.graphics.command_data.opcode==GFX_CMD_END_FRAME)in_frame=0;
        end
    end
    task automatic capture(input string name);
        integer fd,world_pixels,meta,cpu_work,active,frame_work;
        logic [7:0] index; logic [23:0] rgb; renderer_stats_t stats;
        begin
            fd=$fopen({"build/",CAPTURE_PREFIX,"-",name,".ppm"},"w");
            if(!fd) $fatal(1,"Cannot capture Quake frame");
            $fdisplay(fd,"P3\n320 240\n255"); world_pixels=0;
            for(integer i=0;i<76800;i=i+1) begin
                index=`QDISPLAY.front_page_pixel ? pixels1[i] : pixels0[i]; rgb=colors[index];
                if(index!=0) world_pixels=world_pixels+1;
                $fdisplay(fd,"%0d %0d %0d",rgb[23:16],rgb[15:8],rgb[7:0]);
            end
            $fclose(fd);
            if(world_pixels<MIN_WORLD_PIXELS) $fatal(1,"Original room not visible: %0d pixels",world_pixels);
            stats=dut.soc.memory.mmio.stats_snapshot;
            active=stats.total_cycles-stats.swap_wait_cycles;
            cpu_work=dut.soc.memory.ram.mem[CPU_CYCLES_ADDR>>2];
            frame_work=FRAME_CYCLES_ADDR ? dut.soc.memory.ram.mem[FRAME_CYCLES_ADDR>>2] : active+cpu_work;
            if((EXPECTED_TRIANGLES && !INTERACTIVE && stats.triangles_submitted!=EXPECTED_TRIANGLES) ||
               (INTERACTIVE && (stats.triangles_submitted<EXPECTED_TRIANGLES || stats.triangles_submitted>1600)) || (ENFORCE_BUDGET && frame_work>1666667))
                $fatal(1,"Render count/frame budget tri=%0d cycles=%0d",stats.triangles_submitted,frame_work);
            $display("Frame work cycles=%0d CPU submit=%0d GPU active=%0d",frame_work,cpu_work,active);
            meta=$fopen({"build/",CAPTURE_PREFIX,"-",name,".ppm.json"},"w");
            $fdisplay(meta,"{\"triangles\":%0d,\"gpu_active_cycles\":%0d,\"cpu_cycles\":%0d,\"frame_work_cycles\":%0d,\"wall_clock_measured\":%0d,\"world_pixels\":%0d,\"x\":%0d,\"y\":%0d,\"z\":%0d,\"view\":[%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d]}",
                stats.triangles_submitted,active,cpu_work,frame_work,FRAME_CYCLES_ADDR!=0,world_pixels,
                $signed(dut.soc.memory.ram.mem[PLAYER_ADDR>>2]),
                $signed(dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+1]),
                $signed(dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+2]),
                $signed(view.m00),$signed(view.m01),$signed(view.m02),$signed(view.m03),
                $signed(view.m10),$signed(view.m11),$signed(view.m12),$signed(view.m13),
                $signed(view.m20),$signed(view.m21),$signed(view.m22),$signed(view.m23));
            $fclose(meta);
            $display("Captured Quake %s: %0d world pixels",name,world_pixels);
        end
    endtask
    initial begin
        repeat(5) @(posedge clk); #1; KEY=3; wait(phy_ready);
        send_control(0,0,0,0); send_load(123,4,0,0,0,0,0);
        if(dut.load_hold) $fatal(1,"Quake COMMIT failed");
        wait(dut.soc.scratch!=0);
        if(dut.soc.scratch[31:16]==16'hdead) $fatal(1,"Quake firmware failed");
        capture("standing");standing_y=$signed(dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+1]);
        if(STANDING_ONLY) begin $display("PASS %s",TEST_NAME);$finish;end
        if(INTERACTIVE)send_input(1,20,16,8,0);else send_control(1,22,0,0);
        if(dut.network_buttons!=(INTERACTIVE?20:22)) $fatal(1,"Quake UDP input failed");
        wait(changed_frame!=0); wait(dut.soc.scratch==changed_frame);
        if(dut.soc.error_flags || dut.network_error || tx_er ||
            $signed(dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+2])<=0 ||
            $signed(dut.soc.memory.ram.mem[(PLAYER_ADDR>>2)+1])<=standing_y)
            $fatal(1,"Quake turn/movement/render failed");
        capture("moving");
        if(INTERACTIVE && (dut.soc.memory.ram.mem[(DEMO_STATE_ADDR>>2)+7]!=16 ||
            dut.soc.memory.ram.mem[(DEMO_STATE_ADDR>>2)+8]!=8))$fatal(1,"Mouse look not consumed by RV32I");
        $display("PASS %s (same SDRAM SoC, original E1M1, MII first-person turn/walk/jump, %0d triangles, post-depth VGA)",TEST_NAME,EXPECTED_TRIANGLES); $finish;
    end
    initial begin repeat(18000000) @(posedge clk); $fatal(1,"Quake timeout PC=%h scratch=%h",dut.soc.debug_pc,dut.soc.scratch); end
endmodule
`undef QDISPLAY
