`timescale 1ns/1ps
module sdram_memory_tb #(parameter CACHE_ENABLED=1, BURST_ENABLED=1);
    logic clk=0, reset=1; always #10 clk=~clk;
    logic [31:0] addr=0,wdata=0,rdata;
    logic [2:0] funct3=2;
    logic read_en=0,write_en=0,stall,bad,performed,initialized;
    logic load_hold=0,load_valid=0,load_ready;
    logic [31:0] load_addr=0,load_rdata;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    logic [31:0] refresh_count;
    soc_memory #(.HEX_FILE(""),.ENABLE_SDRAM(1),.ENABLE_CACHE(CACHE_ENABLED),.ENABLE_BURST(BURST_ENABLED)) dut (
        .clk(clk),.reset(reset),.sdram_reset(reset),.pc(32'b0),.addr(addr),.wdata(wdata),
        .funct3(funct3),.read_en(read_en),.write_en(write_en),.rdata(rdata),
        .cpu_stall(stall),.misaligned(bad),.write_performed(performed),
        .sdram_initialized(initialized),.refresh_count(refresh_count),
        .load_hold(load_hold),.load_valid(load_valid),.load_write(1'b0),
        .load_addr(load_addr),.load_wdata(32'b0),.load_ready(load_ready),.load_rdata(load_rdata),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);
    integer last_access_cycles,cold_cycles,repeat_cycles,read_before,cold_commands,base,loader_cycles;
    task automatic access(input bit writing,input [31:0] a,v,input [2:0] f,input [31:0] expected);
        integer cycles;
        @(posedge clk); #1; addr=a; wdata=v; funct3=f; read_en=!writing; write_en=writing;
        #1; if (!stall) $fatal(1,"Missing memory stall");
        cycles=0;
        do begin @(posedge clk); cycles=cycles+1; end while(stall);
        if (cycles<2 || cycles>200 || bad || (writing && !performed)) $fatal(1,"Bad memory completion cycles=%0d",cycles);
        if (!writing && rdata!==expected) $fatal(1,"Read %h got %h expected %h",a,rdata,expected);
        last_access_cycles=cycles;
        #1; read_en=0; write_en=0;
    endtask
    initial begin
        repeat(5) @(posedge clk); #1; reset=0;
        wait(initialized); if (chip.refreshes!=8 || !chip.mode_set) $fatal(1,"Initialization");
        access(1,32'h80000000,32'h12345678,2,0);
        access(1,32'h80000001,32'h80,0,0);
        access(1,32'h80000002,32'h8123,1,0);
        read_before=chip.read_commands;
        access(0,32'h80000000,0,2,32'h81238078);
        cold_cycles=last_access_cycles;
        cold_commands=chip.read_commands-read_before;
        if(cold_commands!=(CACHE_ENABLED && !BURST_ENABLED?8:1)) $fatal(1,"Cache fill SDRAM read commands=%0d",cold_commands);
        access(0,32'h80000000,0,2,32'h81238078);
        repeat_cycles=last_access_cycles;
        if(CACHE_ENABLED && repeat_cycles>=cold_cycles) $fatal(1,"Cached repeat must reduce simulated wait");
        access(0,32'h80000001,0,0,32'hffffff80);
        access(0,32'h80000001,0,4,32'h80);
        access(0,32'h80000002,0,1,32'hffff8123);
        access(0,32'h80000002,0,5,32'h8123);
        access(0,32'h80000000,0,2,32'h81238078); // same address consecutive requests
        access(0,32'h80000000,0,2,32'h81238078);
        for(integer i=0;i<25;i=i+1) access(1,32'h80000000+(4<<i),32'h55aa0000+i,2,0);
        for(integer i=0;i<25;i=i+1) access(0,32'h80000000+(4<<i),0,2,32'h55aa0000+i);
        access(1,32'h87fffffc,32'h89abcdef,2,0);
        repeat(4000) @(posedge clk);
        access(0,32'h87fffffc,0,2,32'h89abcdef);
        // Every critical-word position must return the right beat. Distinct
        // words at bank/row ends also catch duplicated, shifted or wrapped data.
        for(integer k=0;k<8;k=k+1) begin
            base=32'h80000fe0+(k<<12);
            for(integer j=0;j<8;j=j+1) access(1,base+4*j,32'ha5010000+256*k+j,2,0);
            read_before=chip.read_commands;
            access(0,base+4*k,0,2,32'ha5010000+256*k+k);
            if(chip.read_commands-read_before!=(CACHE_ENABLED && !BURST_ENABLED?8:1)) $fatal(1,"Offset fill count");
            for(integer j=0;j<8;j=j+1) access(0,base+4*j,0,2,32'ha5010000+256*k+j);
        end
        @(posedge clk); #1; addr=32'h80000001; funct3=2; write_en=1;
        #1; if (!bad || stall || performed) $fatal(1,"Misaligned access");
        @(posedge clk); #1; write_en=0;
        access(0,32'h80000000,0,2,32'h81238078);
        // Exercise the actual loader bus mux and cache bypass, not a forced
        // internal signal. Single reads must expose only the requested word.
        @(posedge clk); #1; load_hold=1;load_valid=1;load_addr=32'h80000000;
        loader_cycles=0;
        do begin @(posedge clk);loader_cycles=loader_cycles+1;end while(!load_ready);
        if(load_rdata!==32'h81238078) $fatal(1,"Loader bypass read mismatch");
        #1;load_valid=0;load_hold=0;
        if (refresh_count<10) $fatal(1,"Idle refresh missing");
        $display("SDRAM_ACCESS cache_enabled=%0d burst_enabled=%0d cold_read_cycles=%0d repeated_read_cycles=%0d cold_read_commands=%0d (real controller/device simulation, not physical board)",CACHE_ENABLED,BURST_ENABLED,cold_cycles,repeat_cycles,cold_commands);
        $display("SDRAM_LOADER cache_enabled=%0d burst_enabled=%0d bypass_read_cycles=%0d",CACHE_ENABLED,BURST_ENABLED,loader_cycles);
        $display("PASS sdram_memory_tb (init, 32-bit map, all address lines, byte masks, signed loads, refresh)"); $finish;
    end
    initial begin #2000000; $fatal(1,"SDRAM memory timeout"); end
endmodule
