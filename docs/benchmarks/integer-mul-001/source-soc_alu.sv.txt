// RV32I ALU plus MUL only. Low 32 bits are identical for signed/unsigned operands.
// Single EX cycle; existing forwarding, writeback and global memory hold apply.
module soc_ALU (
    input logic [31:0] A, B,
    input logic [3:0] ALU_Sel,
    output logic [31:0] ALU_result,
    output logic ALU_Zero
);
    wire [31:0] base_result;
    wire unused_zero;
    wire [31:0] product = A * B;
    ALU base(.A(A),.B(B),.ALU_Sel(ALU_Sel),
             .ALU_result(base_result),.ALU_Zero(unused_zero));
    assign ALU_result = ALU_Sel == 4'b1011 ? product : base_result;
    assign ALU_Zero = ALU_result == 32'b0;
endmodule
