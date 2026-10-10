`timescale 1ns/1ps
module cpu_counter_pipeline_tb;
    logic clk=0, rst=1, soc_stall=0;
    logic [31:0] instruction=32'h13;
    wire [31:0] pc, trace_pc, trace_rd_data;
    wire trace_valid, trace_reg_write;
    wire [4:0] trace_rd;
    wire [159:0] cpu_statistics;
    integer retired_count=0;
    logic done=0;
    always #5 clk=~clk;
    RV32I_SoC cpu(.clk(clk),.rst(rst),.soc_stall(soc_stall),.debug_pc(pc),
        .soc_instruction(instruction),.soc_rdata(32'd7),.soc_misaligned(1'b0),
        .soc_write_performed(1'b0),.cpu_statistics(cpu_statistics),
        .trace_valid(trace_valid),.trace_pc(trace_pc),.trace_rd(trace_rd),
        .trace_reg_write(trace_reg_write),.trace_rd_data(trace_rd_data));
    always @(negedge clk) begin
        case(pc)
            0: instruction<=32'h02000093; // addi x1,zero,32
            4: instruction<=32'h0000a103; // lw x2,0(x1)
            8: instruction<=32'h002101b3; // add x3,x2,x2
            12: instruction<=32'h00318463; // beq x3,x3,+8
            16: instruction<=32'h00100213; // must flush
            20: instruction<=32'h00900293; // addi x5,zero,9
            default: instruction<=32'h0000006f;
        endcase
    end
    always @(posedge clk) if(!rst && trace_valid) begin
        case(retired_count)
            0: if(trace_pc!==0)$fatal(1,"first retirement");
            1: if(trace_pc!==4 || trace_rd_data!==7)$fatal(1,"load");
            2: if(trace_pc!==8 || trace_rd_data!==14)$fatal(1,"forward/load-use");
            3: if(trace_pc!==12)$fatal(1,"branch");
            4: begin
                if(trace_pc!==20 || trace_rd!==5 || trace_rd_data!==9)$fatal(1,"flush");
                done=1;
            end
        endcase
        retired_count=retired_count+1;
    end
    initial begin
        repeat(3)@(negedge clk);rst=0;
        wait(cpu.stall); @(negedge clk);soc_stall=1;
        repeat(8)@(posedge clk);@(negedge clk);soc_stall=0;
        wait(done);#1;
        if(cpu_statistics[127:96]!==5 || cpu_statistics[95:64]!==8 ||
           cpu_statistics[63:32]!==1 || cpu_statistics[31:0]<1)
            $fatal(1,"integrated physical counters %h",cpu_statistics);
        $display("PASS cpu_counter_pipeline_tb");$finish;
    end
    initial begin #10000;$fatal(1,"timeout");end
endmodule
