module soc_IF_ID(
    input logic enable,
    input logic clk, rst, stall, flush,
    input logic valid_IF,
    input logic [31:0] Instruction_IF, pc_IF,
    output logic valid_ID,
    output logic [31:0] Instruction_ID, pc_ID
);
    always_ff @(posedge clk) begin
        if (rst || enable) begin
        if (rst || flush) begin 
            Instruction_ID <= 32'h00000013; //addi x0, x0, 0 aka NOP
            pc_ID <= 32'b0;
            valid_ID <= 1'b0;
        end else if (!stall) begin
            Instruction_ID <= Instruction_IF;
            pc_ID <= pc_IF;
            valid_ID <= valid_IF;
        end
        end
    end
endmodule
