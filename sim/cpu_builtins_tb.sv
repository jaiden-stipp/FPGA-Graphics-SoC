`timescale 1ns/1ps
module cpu_builtins_tb;
    logic clk=0,reset=1;
    always #10 clk=~clk;
    wire [31:0] pc,addr,wdata,instruction,rdata,scratch;
    wire [2:0] funct3;
    wire read_en,write_en,misaligned,write_performed;
    RV32I_SoC cpu(.clk(clk),.rst(reset),.soc_stall(1'b0),.debug_pc(pc),
        .soc_instruction(instruction),.soc_rdata(rdata),.soc_misaligned(misaligned),
        .soc_write_performed(write_performed),.soc_addr(addr),.soc_wdata(wdata),
        .soc_funct3(funct3),.soc_read_en(read_en),.soc_write_en(write_en));
    soc_memory #(.HEX_FILE("build/builtins-test/probe.hex")) memory (
        .clk(clk),.reset(reset),.pc(pc),.addr(addr),.wdata(wdata),.funct3(funct3),
        .read_en(read_en),.write_en(write_en),.instruction(instruction),.rdata(rdata),
        .misaligned(misaligned),.write_performed(write_performed),.scratch(scratch),
        .byte_ready(1'b1),.decoder_error(1'b0),.command_error(1'b0),.frame_done(1'b0),
        .frame_done_id(32'b0),.frame_statistics(416'b0),.buttons(8'b0));
    always @(posedge clk) if(!reset && instruction[6:0]==7'h33 && instruction[31:25]==7'h01)
        $fatal(1,"Baseline compiler helper attempted M instruction at %h",pc);
    initial begin
        repeat(5) @(negedge clk);reset=0;
        repeat(200000) begin
            @(posedge clk);#1;
            if(scratch===32'hdead0001) $fatal(1,"Software multiply mismatch");
            if(scratch===32'h0600db17) begin
                $display("PASS cpu_builtins_tb (164 products, baseline RV32I, no M instructions)");$finish;
            end
        end
        $fatal(1,"Software multiply CPU timeout pc=%h",pc);
    end
endmodule
