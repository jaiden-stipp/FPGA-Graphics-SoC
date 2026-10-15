`timescale 1ns/1ps
`include "renderer_types.svh"
// Two real CPU/cache/SDRAM/GPU systems, including original actors and game port.
// Old package versus geometry-enabled package; compare the first three frames.
module geometry_game_tb;
    logic clk=0,reset=1;
    always #10 clk=~clk;
    integer captured[0:1];
    genvar g;
    generate for(g=0;g<2;g=g+1)begin:variants
        wire[31:0]scratch,pc;wire[3:0]errors;wire initialized;
        wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
        wire[12:0]DRAM_ADDR;wire[1:0]DRAM_BA;wire[3:0]DRAM_DQM;wire[31:0]DRAM_DQ;
        localparam HEX=g==0?"build/mario-castle-sdram-direct-packed-mul-test.hex":"build/mario-castle-sdram-direct-packed-mul-geometry-test.hex";
        soc_top #(.HEX_FILE(HEX),.ENABLE_SDRAM(1)) dut(
            .clk(clk),.reset(reset),.sdram_reset(reset),.buttons(8'd0),.debug_pc(pc),.scratch(scratch),.error_flags(errors),
            .sdram_initialized(initialized),.DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
            .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
            .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
        sdram_device_model chip(.*);
        reg[7:0]page0[0:76799],page1[0:76799],depth[0:76799];reg[23:0]palette[0:255];
        integer commands,fd;
        initial begin
            captured[g]=0;
            for(integer i=0;i<76800;i++)begin page0[i]=0;page1[i]=0;depth[i]=0;end
            for(integer i=0;i<256;i++)palette[i]=0;
            commands=$fopen($sformatf("build/arch-stage5/game-%0d.commands.log",g),"w");
        end
        initial begin:preload
            integer file,index,rc;reg[31:0]word;
            wait(initialized);
            file=$fopen("build/mario-castle-sdram-direct-packed-mul.assets.hex","r");if(!file)$fatal(1,"missing accepted assets");
            index=0;
            while(!$feof(file))begin
                rc=$fscanf(file,"%h\n",word);
                if(rc==1)begin chip.write_word(index,word);index++;end
            end
            $fclose(file);
        end
        for(genvar b=0;b<2;b++)begin:bank_capture
            always @(negedge clk)begin
                if(dut.graphics.renderer.pipeline.display.framebuffer0.banks[b].ram_write_enable)
                    page0[(dut.graphics.renderer.pipeline.display.framebuffer0.banks[b].ram_write_address<<1)+b]=dut.graphics.renderer.pipeline.display.framebuffer0.banks[b].ram_write_data;
                if(dut.graphics.renderer.pipeline.display.framebuffer1.banks[b].ram_write_enable)
                    page1[(dut.graphics.renderer.pipeline.display.framebuffer1.banks[b].ram_write_address<<1)+b]=dut.graphics.renderer.pipeline.display.framebuffer1.banks[b].ram_write_data;
                if(dut.graphics.renderer.pipeline.depth_memory.banks[b].ram_write_enable)
                    depth[(dut.graphics.renderer.pipeline.depth_memory.banks[b].ram_write_address<<1)+b]=dut.graphics.renderer.pipeline.depth_memory.banks[b].ram_write_depth;
            end
        end
        always @(negedge clk)if(!dut.system_reset)begin
            if(errors || scratch[31:16]==16'hdead)$fatal(1,"game protocol failure variant=%0d pc=%h scratch=%h errors=%h",g,pc,scratch,errors);
            if(dut.graphics.renderer.pipeline.palette_write)
                palette[dut.graphics.renderer.pipeline.palette_address]=dut.graphics.renderer.pipeline.palette_write_rgb;
            if(captured[g]<3 && dut.graphics.command_valid && dut.graphics.command_ready)
                $fdisplay(commands,"%h",dut.graphics.command_data);
            if(captured[g]<3 && dut.frame_done)begin
                if(dut.frame_done_id!=captured[g]+1)$fatal(1,"game frame order");
                fd=$fopen($sformatf("build/arch-stage5/game-%0d-frame-%0d.color.hex",g,dut.frame_done_id),"w");
                for(integer i=0;i<76800;i++)$fdisplay(fd,"%02h",dut.graphics.renderer.pipeline.display.front_page_pixel?page1[i]:page0[i]);$fclose(fd);
                fd=$fopen($sformatf("build/arch-stage5/game-%0d-frame-%0d.depth.hex",g,dut.frame_done_id),"w");
                for(integer i=0;i<76800;i++)$fdisplay(fd,"%02h",depth[i]);$fclose(fd);
                fd=$fopen($sformatf("build/arch-stage5/game-%0d-frame-%0d.palette.hex",g,dut.frame_done_id),"w");
                for(integer i=0;i<256;i++)$fdisplay(fd,"%06h",palette[i]);$fclose(fd);
                captured[g]++;
                $display("GAME_CAPTURE variant=%0d frame=%0d time=%0t",g,dut.frame_done_id,$time);
                if(captured[g]==3)$fclose(commands);
            end
        end
    end endgenerate
    initial begin repeat(12)@(negedge clk);reset=0;
        wait(captured[0]==3 && captured[1]==3);
        $display("PASS geometry_game_tb: six complete CPU/game/GPU frames captured; host exact comparison required");$finish;
    end
    initial begin repeat(18000000)@(posedge clk);$fatal(1,"full-game equivalence timeout");end
endmodule
