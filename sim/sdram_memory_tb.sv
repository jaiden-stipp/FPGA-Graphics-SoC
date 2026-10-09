`timescale 1ns/1ps
module sdram_memory_tb #(parameter CACHE_ENABLED=1);
    logic clk=0, reset=1; always #10 clk=~clk;
    logic [31:0] addr=0,wdata=0,rdata;
    logic [2:0] funct3=2;
    logic read_en=0,write_en=0,stall,bad,performed,initialized;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    logic [31:0] refresh_count;
    soc_memory #(.HEX_FILE(""),.ENABLE_SDRAM(1),.ENABLE_CACHE(CACHE_ENABLED)) dut (
        .clk(clk),.reset(reset),.sdram_reset(reset),.pc(32'b0),.addr(addr),.wdata(wdata),
        .funct3(funct3),.read_en(read_en),.write_en(write_en),.rdata(rdata),
        .cpu_stall(stall),.misaligned(bad),.write_performed(performed),
        .sdram_initialized(initialized),.refresh_count(refresh_count),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);
    integer last_access_cycles,cold_cycles,repeat_cycles;
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
        access(0,32'h80000000,0,2,32'h81238078);
        cold_cycles=last_access_cycles;
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
        @(posedge clk); #1; addr=32'h80000001; funct3=2; write_en=1;
        #1; if (!bad || stall || performed) $fatal(1,"Misaligned access");
        @(posedge clk); #1; write_en=0;
        access(0,32'h80000000,0,2,32'h81238078);
        if (refresh_count<10) $fatal(1,"Idle refresh missing");
        $display("SDRAM_ACCESS cache_enabled=%0d cold_read_cycles=%0d repeated_read_cycles=%0d (real controller/device simulation, not physical board)",CACHE_ENABLED,cold_cycles,repeat_cycles);
        $display("PASS sdram_memory_tb (init, 32-bit map, all address lines, byte masks, signed loads, refresh)"); $finish;
    end
    initial begin #2000000; $fatal(1,"SDRAM memory timeout"); end
endmodule
