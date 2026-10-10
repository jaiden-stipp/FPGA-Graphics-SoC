`timescale 1ns/1ps
module cpu_mul_tb;
    logic clk=0,rst=1,soc_stall=0;
    logic [31:0] instruction=32'h13;
    wire [31:0] pc,trace_pc,trace_rd_data;
    wire trace_valid,trace_reg_write;
    wire [4:0] trace_rd;
    wire [159:0] cpu_statistics;
    logic [31:0] rom[0:4095],expected[0:4095];
    logic check_write[0:4095],forbidden[0:4095];
    integer n=0,retired=0,expected_retired=0;
    logic done=0;
    always #5 clk=~clk;
    RV32I_SoC cpu(.clk(clk),.rst(rst),.soc_stall(soc_stall),.debug_pc(pc),
        .soc_instruction(instruction),.soc_rdata(32'd7),.soc_misaligned(1'b0),
        .soc_write_performed(1'b0),.cpu_statistics(cpu_statistics),
        .trace_valid(trace_valid),.trace_pc(trace_pc),.trace_rd(trace_rd),
        .trace_reg_write(trace_reg_write),.trace_rd_data(trace_rd_data));
    task emit(input logic[31:0] insn,value,input logic wr);
        rom[n]=insn;expected[n]=value;check_write[n]=wr;forbidden[n]=0;
        ++n;++expected_retired;
    endtask
    task constant(input logic[4:0] rd,input logic[31:0] value);
        logic[31:0] upper;
        upper=(value+32'h800)&32'hfffff000;
        emit(upper|{20'b0,rd,7'h37},upper,1);
        emit({value[11:0],rd,3'b000,rd,7'h13},value,1);
    endtask
    task pair(input logic[31:0] a,b);
        logic[31:0] low,twice;
        logic[63:0] wide;
        wide={32'b0,a}*{32'b0,b};low=wide[31:0];twice=low+low;
        constant(1,a);constant(2,b);
        emit({7'h01,5'd2,5'd1,3'd0,5'd3,7'h33},low,1);
        emit({7'h00,5'd3,5'd3,3'd0,5'd4,7'h33},twice,1);
        // Consecutive dependent multiply uses forwarded ADD result.
        emit({7'h01,5'd1,5'd4,3'd0,5'd5,7'h33},twice*a,1);
    endtask
    always @(negedge clk) instruction<=pc[31:14]==0?rom[pc[13:2]]:32'h0000006f;
    always @(posedge clk) if(!rst && trace_valid) begin
        if(forbidden[trace_pc>>2])$fatal(1,"flushed MUL retired");
        if(check_write[trace_pc>>2] && (!trace_reg_write || trace_rd_data!==expected[trace_pc>>2]))
            $fatal(1,"MUL/forward mismatch pc=%h got=%h expected=%h",trace_pc,trace_rd_data,expected[trace_pc>>2]);
        if(!check_write[trace_pc>>2] && trace_reg_write)$fatal(1,"unsupported M/x0 writes");
        ++retired;
        if(trace_rd==31 && trace_reg_write)done=1;
    end
    initial begin
        for(integer i=0;i<4096;++i)begin rom[i]=32'h0000006f;check_write[i]=0;forbidden[i]=0;end
        pair(0,32'hffffffff);pair(32'hffffffff,32'hffffffff);
        pair(32'h80000000,2);pair(32'h80000000,32'hffffffff);
        pair(32'h7fffffff,32'h7fffffff);pair(32'h12345678,32'hfedcba98);
        for(integer i=0;i<128;++i)pair($urandom,$urandom);
        emit(32'h00002303,7,1); // lw x6,0(zero)
        emit({7'h01,5'd6,5'd6,3'd0,5'd7,7'h33},49,1); // dependent load/MUL
        emit({7'h01,5'd7,5'd7,3'd0,5'd0,7'h33},2401,1); // trace reports intent; register file suppresses x0
        emit(32'h01300413,19,1); // prove x0 remained zero
        emit(32'h00738463,0,0); // taken beq x7,x7,+8
        emit({7'h01,5'd7,5'd7,3'd0,5'd9,7'h33},0,0);
        forbidden[n-1]=1;--expected_retired;
        // Unsupported MULH/DIV encodings must not alias RV32I writes.
        for(integer k=1;k<8;++k)emit({7'h01,5'd7,5'd7,3'(k),5'd10,7'h33},0,0);
        emit(32'h06300f93,99,1);
        repeat(3)@(negedge clk);rst=0;
        wait(cpu.valid_EX && cpu.ctrl_EX.ALU_Sel==4'b1011);
        @(negedge clk);soc_stall=1;
        repeat(8)@(posedge clk);@(negedge clk);soc_stall=0;
        wait(cpu.stall);@(negedge clk);soc_stall=1;
        repeat(8)@(posedge clk);@(negedge clk);soc_stall=0;
        wait(done);#1;
        if(retired!=expected_retired || cpu_statistics[127:96]!==expected_retired || cpu_statistics[95:64]!==16)
            $fatal(1,"duplicate/lost retirement or freeze accounting");
        $display("PASS cpu_mul_tb: 134 operand pairs, forwarding, load-use, x0, branch flush, unsupported M, 16 freeze cycles");$finish;
    end
    initial begin #100000;$fatal(1,"timeout");end
endmodule
