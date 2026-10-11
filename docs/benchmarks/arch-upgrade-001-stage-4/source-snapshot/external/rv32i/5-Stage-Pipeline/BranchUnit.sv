module BranchUnit(
    input  logic jump, jalr, branch, ALU_Zero,
    input  logic [2:0] funct3,
    input  logic [31:0] imm_EX, ALU_result, pc_EX,
    output logic [31:0] pc_target,
    output logic pc_src
);
    logic comparison_result;

    always_comb begin
        pc_target = jalr ? (ALU_result & 32'hffff_fffe): (pc_EX + imm_EX);

        comparison_result = 1'b0;
        pc_src = 1'b0;

        case (funct3)
            3'b000: comparison_result = ALU_Zero;       // beq
            3'b001: comparison_result = ~ALU_Zero;      // bne
            3'b100: comparison_result = ALU_result[0];  // blt
            3'b101: comparison_result = ~ALU_result[0]; // bge
            3'b110: comparison_result = ALU_result[0];  // bltu
            3'b111: comparison_result = ~ALU_result[0]; // bgeu
            default: comparison_result = 1'b0;
        endcase

        pc_src = jump | jalr | (branch & comparison_result);
    end
endmodule