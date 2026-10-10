`timescale 1ns/1ps
module soc_cpu_counters_tb;
    logic clk=0, reset=1, memory_freeze=0, retired=0, dependency=0, redirect=0;
    wire [159:0] statistics;
    always #5 clk=~clk;
    soc_cpu_counters dut(.*);
    task automatic step(input logic m,r,d,b);
        @(negedge clk); memory_freeze=m; retired=r; dependency=d; redirect=b;
        @(posedge clk); #1;
    endtask
    initial begin
        @(posedge clk); #1;
        if(statistics!==0)$fatal(1,"reset");
        @(negedge clk); reset=0;
        // This edge is an active empty pipeline cycle.
        @(posedge clk); #1;
        step(0,1,0,0);
        step(1,1,1,1); step(1,1,1,1); step(1,1,1,1);
        step(0,1,1,0); step(0,1,1,1);
        if(statistics!=={32'd7,32'd3,32'd3,32'd1,32'd1})
            $fatal(1,"exclusive counters/held signal qualification %h",statistics);
        @(negedge clk); reset=1;
        @(posedge clk); #1;
        if(statistics!==0)$fatal(1,"restart");
        $display("PASS soc_cpu_counters_tb"); $finish;
    end
endmodule
