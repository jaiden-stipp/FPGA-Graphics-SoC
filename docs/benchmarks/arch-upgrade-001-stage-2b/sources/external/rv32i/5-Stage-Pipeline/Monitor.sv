module Monitor (
    input logic clk, rst, instruction_retired, stall, flush, forward, 
    output logic [31:0] instruction_counter, cycle_counter, stall_counter, flush_counter, forward_counter
);
    always_ff @(posedge clk) begin
        if (rst) begin
            instruction_counter <= 32'b0;
            cycle_counter <= 32'b0;
            stall_counter <= 32'b0;
            flush_counter <= 32'b0;
            forward_counter <= 32'b0;
        end else begin
            cycle_counter <= cycle_counter + 1;
            if (stall) stall_counter <= stall_counter + 1;
            if (instruction_retired) instruction_counter <= instruction_counter + 1;
            if (flush) flush_counter <= flush_counter + 1;
            if (forward) forward_counter <= forward_counter + 1;
        end
    end
endmodule