`timescale 1ns/1ps
module cpu_geometry_tb;
    logic clk=0,reset=1;always #10 clk=~clk;
    wire[31:0]pc,addr,wdata,rdata,instruction,scratch;
    wire[2:0]funct3;wire rd,wr,bad,performed;wire[3:0]errors;
    RV32I_SoC cpu(.clk(clk),.rst(reset),.soc_stall(1'b0),.debug_pc(pc),.soc_instruction(instruction),
        .soc_rdata(rdata),.soc_misaligned(bad),.soc_write_performed(performed),
        .soc_addr(addr),.soc_wdata(wdata),.soc_funct3(funct3),.soc_read_en(rd),.soc_write_en(wr));
    soc_memory #(.HEX_FILE("build/arch-stage5/probe.hex")) memory(
        .clk(clk),.reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(funct3),.read_en(rd),.write_en(wr),
        .instruction(instruction),.rdata(rdata),.misaligned(bad),.write_performed(performed),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'd0),.frame_statistics(416'd0),.buttons(8'd0),.error_flags(errors),.scratch(scratch));
    always @(posedge clk)if(!reset)begin
        if(errors || scratch[31:16]==16'hdead)$fatal(1,"CPU geometry protocol/equivalence failure scratch=%h errors=%h pc=%h",scratch,errors,pc);
        if(scratch==32'h3500600d)begin $display("PASS cpu_geometry_tb: production transform/outcodes and real CPU MMIO adapter");$finish;end
    end
    initial begin repeat(6)@(negedge clk);reset=0;end
    initial begin #50000000;$fatal(1,"CPU geometry timeout pc=%h scratch=%h",pc,scratch);end
endmodule
