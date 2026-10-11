import pipeline_pkg::*;

module ImmGen(
    input logic [31:0] Instruction,
    input logic [2:0] imm_sel,
    output logic [31:0] imm_out
);
    always_comb begin
        case (imm_sel)
            I_TYPE: imm_out = {{20{Instruction[31]}}, Instruction[31:20]};
            S_TYPE: imm_out = {{20{Instruction[31]}}, Instruction[31:25], Instruction[11:7]};
            B_TYPE: imm_out = {{20{Instruction[31]}}, Instruction[7], Instruction[30:25], Instruction[11:8], 1'b0};
            U_TYPE: imm_out = {Instruction[31:12], 12'b0};
            J_TYPE: imm_out = {{12{Instruction[31]}}, Instruction[19:12], Instruction[20], Instruction[30:21], 1'b0};
            default: imm_out = 32'd0;
        endcase
    end
endmodule
