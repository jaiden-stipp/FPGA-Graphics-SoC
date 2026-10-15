`timescale 1ns/1ps
`include "renderer_types.svh"
// Two real CPU/cache/SDRAM/GPU systems, including original actors and game port.
// Old package versus geometry-enabled package; compare the first three frames.
module geometry_stream_tb;
    logic clk=0,reset=1;
    always #10 clk=~clk;
    integer captured[0:1];
    genvar g;
    generate for(g=0;g<2;g=g+1)begin:variants
        wire[31:0]scratch,pc;wire[3:0]errors;wire initialized;
        wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
        wire[12:0]DRAM_ADDR;wire[1:0]DRAM_BA;wire[3:0]DRAM_DQM;wire[31:0]DRAM_DQ;
        localparam HEX=g==0?"build/mario-castle-sdram-direct-packed-mul-test.hex":"build/mario-castle-sdram-direct-packed-mul-geometry-test.hex";
        wire[31:0]addr,wdata,rdata,instruction;
        wire[2:0]funct3;wire rd,wr,bad,performed,stall;
        wire[7:0]byte_data;wire byte_valid,byte_ready,decoder_error;
        logic frame_done=0;logic[31:0]frame_id=0;
        logic command_ready=1;wire command_valid;
        graphics_command_t command;
        wire sysreset=reset || !initialized;
        RV32I_SoC cpu(.clk(clk),.rst(sysreset),.soc_stall(stall),.debug_pc(pc),.soc_instruction(instruction),
            .soc_rdata(rdata),.soc_misaligned(bad),.soc_write_performed(performed),
            .soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),.soc_read_en(rd),.soc_write_en(wr));
        soc_memory #(.HEX_FILE(HEX),.ENABLE_SDRAM(1)) memory(
            .clk(clk),.reset(sysreset),.sdram_reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(funct3),
            .read_en(rd),.write_en(wr),.instruction(instruction),.rdata(rdata),.misaligned(bad),.write_performed(performed),
            .byte_data(byte_data),.byte_valid(byte_valid),.byte_ready(byte_ready),.decoder_error(decoder_error),
            .command_error(1'b0),.frame_done(frame_done),.frame_done_id(frame_id),.frame_statistics(416'd0),
            .buttons(8'd0),.error_flags(errors),.scratch(scratch),.cpu_stall(stall),.sdram_initialized(initialized),
            .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),.DRAM_RAS_N(DRAM_RAS_N),
            .DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),.DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ));
        sdram_device_model chip(.*);
        graphics_command_stream_decoder decoder(.clk(~clk),.reset(sysreset),.byte_data(byte_data),.byte_valid(byte_valid),
            .byte_ready(byte_ready),.command_data(command),.command_valid(command_valid),.command_ready(command_ready),.decoder_error(decoder_error));
        integer commands,progress,fd,cycles=0;
        initial begin
            captured[g]=0;
            progress=$fopen($sformatf("build/arch-stage5/stream-%0d.progress.log",g),"w");
            commands=$fopen($sformatf("build/arch-stage5/stream-%0d.commands.log",g),"w");
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
        always @(negedge clk)begin
            cycles++;
            if(cycles%10000==0)begin
                $fdisplay(progress,"cycles=%0d initialized=%b reset=%b pc=%h scratch=%h stall=%b",cycles,initialized,sysreset,pc,scratch,stall);$fflush(progress);
            end
            frame_done<=0;command_ready<=(cycles%11)<7;
            if(!sysreset)begin
                if(errors || scratch[31:16]==16'hdead)$fatal(1,"stream protocol variant=%0d pc=%h scratch=%h errors=%h",g,pc,scratch,errors);
                if(captured[g]<3 && command_valid && command_ready)begin
                    $fdisplay(commands,"%h",command);$fflush(commands);
                    if(command.opcode==GFX_CMD_BEGIN_FRAME)frame_id<=`GFX_ARGUMENT(command);
                    if(command.opcode==GFX_CMD_END_FRAME)begin
                        frame_done<=1;captured[g]++;
                        $display("STREAM_CAPTURE variant=%0d frame=%0d cycles=%0d",g,frame_id,cycles);
                        if(captured[g]==3)$fclose(commands);
                    end
                end
            end
        end
    end endgenerate
    initial begin repeat(12)@(negedge clk);reset=0;
        wait(captured[0]==3 && captured[1]==3);
        $display("PASS geometry_stream_tb: six real CPU/cache/SDRAM game command streams captured; exact comparison and GPU replay required");$finish;
    end
    initial begin repeat(18000000)@(posedge clk);$fatal(1,"full-game equivalence timeout");end
endmodule
