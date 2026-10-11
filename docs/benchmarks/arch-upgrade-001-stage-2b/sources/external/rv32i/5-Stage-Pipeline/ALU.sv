import pipeline_pkg::*;

module ALU (
    input logic [31:0] A, B,
    input logic [3:0] ALU_Sel,
    output logic [31:0] ALU_result,
    output logic ALU_Zero
);
    always_comb begin
        case (ALU_Sel)
            ADD:  ALU_result = A + B;
            SUB:  ALU_result = A - B;
            AND:  ALU_result = A & B;
            OR:   ALU_result = A | B;
            XOR:  ALU_result = A ^ B;
            SLTU: ALU_result = (A < B);
            SLT:  ALU_result = ($signed(A) < $signed(B));
            SLL:  ALU_result = A << B[4:0];
            SRL:  ALU_result = A >> B[4:0];
            SRA:  ALU_result = $signed(A) >>> B[4:0];
            PASSB: ALU_result = B;
            default: ALU_result = 32'b0;
        endcase
    end

    assign ALU_Zero = (ALU_result == 32'b0);
endmodule
