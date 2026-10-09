`timescale 1ns/1ps
`include "renderer_types.svh"
`include "beacon-sdram-test_symbols.svh"
`define BEACON_DISPLAY dut.soc.graphics.renderer.pipeline.display
module beacon_sdram_top_tb;
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
    model_matrix_3x4_t actor,first_actor;
    integer current_frame=0,changed_frame=0; bit got_actor=0;
    de2_115_soc_top #(.HEX_FILE("build/beacon-sdram-test.hex"),.ENABLE_SDRAM(1)) dut (
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
    `include "load_packets.svh"
    initial begin : preload
        integer fd,index,read_count; reg [31:0] value;
        wait(dut.sdram_initialized);
        fd=$fopen("build/beacon-sdram.assets.hex","r"); if(!fd) $fatal(1,"Missing Beacon assets");
        index=0;
        while(!$feof(fd)) begin
            read_count=$fscanf(fd,"%h\n",value);
            if(read_count==1) begin chip.memory[index]=value; index=index+1; end
        end
        $fclose(fd);
    end
    always @(negedge clk) begin
        if (`BEACON_DISPLAY.framebuffer0.ram_write_enable)
            pixels0[`BEACON_DISPLAY.framebuffer0.ram_write_address]=`BEACON_DISPLAY.framebuffer0.ram_write_data;
        if (`BEACON_DISPLAY.framebuffer1.ram_write_enable)
            pixels1[`BEACON_DISPLAY.framebuffer1.ram_write_address]=`BEACON_DISPLAY.framebuffer1.ram_write_data;
        if (`BEACON_DISPLAY.palette_write) colors[`BEACON_DISPLAY.palette_address]=`BEACON_DISPLAY.palette_write_rgb;
        if(dut.soc.graphics.command_valid && dut.soc.graphics.command_ready) begin
            if(dut.soc.graphics.command_data.opcode==GFX_CMD_BEGIN_FRAME)
                current_frame=`GFX_ARGUMENT(dut.soc.graphics.command_data);
            if(dut.soc.graphics.command_data.opcode==GFX_CMD_DRAW_MESH && `GFX_DRAW_MESH_HANDLE(dut.soc.graphics.command_data)==3) begin
                actor=`GFX_MODEL_MATRIX(dut.soc.graphics.command_data);
                if(!got_actor) begin first_actor=actor; got_actor=1; end
                if(actor.m03>first_actor.m03 && actor.m13>first_actor.m13 && !changed_frame) changed_frame=current_frame;
            end
        end
    end
    task automatic capture(input string name);
        integer fd,actor_pixels,beacon_pixels,meta,cpu_work,active;
        logic [7:0] index; logic [23:0] rgb; renderer_stats_t stats;
        begin
            fd=$fopen({"build/beacon-sdram-",name,".ppm"},"w");
            if(!fd) $fatal(1,"Cannot capture Beacon frame");
            $fdisplay(fd,"P3\n320 240\n255"); actor_pixels=0; beacon_pixels=0;
            for(integer i=0;i<76800;i=i+1) begin
                index=`BEACON_DISPLAY.front_page_pixel ? pixels1[i] : pixels0[i]; rgb=colors[index];
                if(index==4) actor_pixels=actor_pixels+1;
                if(index==5) beacon_pixels=beacon_pixels+1;
                $fdisplay(fd,"%0d %0d %0d",rgb[23:16],rgb[15:8],rgb[7:0]);
            end
            $fclose(fd);
            if(actor_pixels<20 || beacon_pixels<10) $fatal(1,"Second game not visible: actor=%0d beacons=%0d",actor_pixels,beacon_pixels);
            stats=dut.soc.memory.mmio.stats_snapshot;
            active=stats.total_cycles-stats.swap_wait_cycles;
            cpu_work=dut.soc.memory.ram.mem[`BEACON_SDRAM_TEST_CPU_CYCLES_ADDR>>2];
            if(stats.triangles_submitted!=62 || active+cpu_work>1666667)
                $fatal(1,"Beacon render count/frame budget tri=%0d cycles=%0d",stats.triangles_submitted,active+cpu_work);
            meta=$fopen({"build/beacon-sdram-",name,".ppm.json"},"w");
            $fdisplay(meta,"{\"triangles\":%0d,\"gpu_active_cycles\":%0d,\"cpu_cycles\":%0d,\"actor_pixels\":%0d,\"beacon_pixels\":%0d,\"x\":%0d,\"y\":%0d,\"grounded\":%0d}",
                stats.triangles_submitted,active,cpu_work,actor_pixels,beacon_pixels,$signed(actor.m03),$signed(actor.m13),
                dut.soc.memory.ram.mem[(`BEACON_SDRAM_TEST_PLAYER_ADDR>>2)+4]);
            $fclose(meta);
            $display("Captured Beacon %s: %0d actor pixels, %0d beacon pixels",name,actor_pixels,beacon_pixels);
        end
    endtask
    initial begin
        repeat(5) @(posedge clk); #1; KEY=3; wait(phy_ready);
        send_control(0,0,0,0); send_load(123,4,0,0,0,0,0);
        if(dut.load_hold) $fatal(1,"Beacon COMMIT failed");
        wait(dut.soc.scratch!=0);
        if(dut.soc.scratch[31:16]==16'hdead) $fatal(1,"Beacon firmware failed");
        capture("standing"); send_control(1,18,0,0);
        if(dut.network_buttons!=18) $fatal(1,"Beacon UDP input failed");
        wait(changed_frame!=0); wait(dut.soc.scratch==changed_frame);
        if(dut.soc.error_flags || dut.network_error || tx_er) $fatal(1,"Beacon renderer errors");
        capture("jumping");
        $display("PASS beacon_sdram_top_tb (same SDRAM CPU/GPU runtime, MII move/jump, 62 triangles, post-depth VGA)"); $finish;
    end
    initial begin repeat(12000000) @(posedge clk); $fatal(1,"Beacon timeout PC=%h scratch=%h",dut.soc.debug_pc,dut.soc.scratch); end
endmodule
`undef BEACON_DISPLAY
