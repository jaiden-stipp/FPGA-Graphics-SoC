`timescale 1ns/1ps
module sdram_cpu_tb #(parameter CACHE_LINE_BYTES=32);
    logic clk=0,reset=1; always #10 clk=~clk;
    logic [31:0] pc,addr,wdata,instruction,rdata,scratch;
    logic [2:0] funct3;
    logic read_en,write_en,bad,performed,stall,initialized;
    logic trace_valid,commit_valid;
    wire DRAM_CLK,DRAM_CKE,DRAM_CS_N,DRAM_RAS_N,DRAM_CAS_N,DRAM_WE_N;
    wire [12:0] DRAM_ADDR; wire [1:0] DRAM_BA; wire [3:0] DRAM_DQM; wire [31:0] DRAM_DQ;
    wire cpu_reset=reset || !initialized;
    RV32I_SoC cpu (
        .clk(clk),.rst(cpu_reset),.debug_pc(pc),.soc_stall(stall),
        .soc_instruction(instruction),.soc_rdata(rdata),.soc_misaligned(bad),.soc_write_performed(performed),
        .soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),.soc_read_en(read_en),.soc_write_en(write_en),
        .trace_valid(trace_valid),.commit_valid(commit_valid)
    );
    soc_memory #(.HEX_FILE("build/sdram-test-sdram.hex"),.ENABLE_SDRAM(1),.CACHE_LINE_BYTES(CACHE_LINE_BYTES)) memory (
        .clk(clk),.reset(cpu_reset),.sdram_reset(reset),.pc(pc),.addr(addr),.wdata(wdata),
        .funct3(funct3),.read_en(read_en),.write_en(write_en),.instruction(instruction),.rdata(rdata),
        .cpu_stall(stall),.misaligned(bad),.write_performed(performed),.sdram_initialized(initialized),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0),.scratch(scratch),
        .DRAM_CLK(DRAM_CLK),.DRAM_CKE(DRAM_CKE),.DRAM_CS_N(DRAM_CS_N),
        .DRAM_RAS_N(DRAM_RAS_N),.DRAM_CAS_N(DRAM_CAS_N),.DRAM_WE_N(DRAM_WE_N),
        .DRAM_ADDR(DRAM_ADDR),.DRAM_BA(DRAM_BA),.DRAM_DQM(DRAM_DQM),.DRAM_DQ(DRAM_DQ)
    );
    sdram_device_model chip(.*);
    integer held_cycles=0;
    logic [159:0] saved_pcs;
    always @(posedge clk) if (stall && !cpu_reset) begin
        saved_pcs={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB};
        if(trace_valid || commit_valid) $fatal(1,"Duplicate retirement during wait");
        #1; if(saved_pcs!=={pc,cpu.pc_ID,cpu.pc_EX,cpu.pc_MEM,cpu.pc_WB}) $fatal(1,"Pipeline changed during wait");
        held_cycles=held_cycles+1;
    end
    initial begin
        repeat(5) @(posedge clk); #1; reset=0;
        wait(scratch==32'h5dad600d || scratch[31:16]==16'hdead);
        if(scratch!=32'h5dad600d || held_cycles<1000 || chip.refreshes<100)
            $fatal(1,"CPU self-test failed: %h held=%0d refreshes=%0d",scratch,held_cycles,chip.refreshes);
        $display("PASS sdram_cpu_tb (real RV32I self-test, all pipeline registers held, %0d wait cycles)",held_cycles); $finish;
    end
    initial begin #120000000; $fatal(1,"CPU SDRAM timeout PC=%h scratch=%h",pc,scratch); end
endmodule
