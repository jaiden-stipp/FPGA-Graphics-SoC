import pipeline_pkg::*;

module ControlUnit(
    input logic [6:0] opcode,
    input logic [2:0] funct3,
    input logic funct7b5,
    input logic [4:0] rdaddr,
    output logic reg_write,
    output logic alu_src,
    output logic [2:0] imm_sel,
    output logic mem_write,
    output logic mem_read,
    output logic branch,
    output logic jump,
    output logic jalr,
    output logic [1:0] result_src,
    output logic [3:0] ALU_Sel,
    output logic [2:0] funct3_o,
    output logic [4:0] rdaddr_o,
    output logic pc_sel
);
    assign funct3_o = funct3;
    assign rdaddr_o = rdaddr;
    assign pc_sel = (opcode == AUIPC);

    always_comb begin
        reg_write = 1'b0; alu_src = 1'b0; imm_sel = 3'b0; mem_write = 1'b0;
        mem_read = 1'b0; branch = 1'b0; jump = 1'b0; jalr = 1'b0;
        result_src = 2'b0; ALU_Sel = 4'b0;
        case (opcode)
            R: begin
                reg_write = 1'b1;
                imm_sel = 3'b000;
                case (funct3)
                    3'b000: ALU_Sel = funct7b5 ? SUB : ADD;
                    3'b001: ALU_Sel = SLL;
                    3'b010: ALU_Sel = SLT;
                    3'b011: ALU_Sel = SLTU;
                    3'b100: ALU_Sel = XOR;
                    3'b101: ALU_Sel = funct7b5 ? SRA : SRL;
                    3'b110: ALU_Sel = OR;
                    3'b111: ALU_Sel = AND;
                    default: ALU_Sel = ADD;
                endcase
            end
            I: begin
                reg_write = 1'b1;
                alu_src = 1'b1;
                case (funct3)
                    3'b000: ALU_Sel = ADD;
                    3'b001: ALU_Sel = SLL;
                    3'b010: ALU_Sel = SLT;
                    3'b011: ALU_Sel = SLTU;
                    3'b100: ALU_Sel = XOR;
                    3'b101: ALU_Sel = funct7b5 ? SRA : SRL;
                    3'b110: ALU_Sel = OR;
                    3'b111: ALU_Sel = AND;
                    default: ALU_Sel = ADD;
                endcase
            end
            L: begin
                reg_write = 1'b1;
                alu_src = 1'b1;
                mem_read = 1'b1;
                result_src = 2'b01;
            end
            S: begin
                alu_src = 1'b1;
                imm_sel = 3'b001;
                mem_write = 1'b1;
                result_src = 2'b00;
            end
            B: begin
                imm_sel = 3'b010;
                branch = 1'b1;
                case (funct3)
                    3'b000, 3'b001: ALU_Sel = SUB;
                    3'b100, 3'b101: ALU_Sel = SLT;
                    3'b110, 3'b111: ALU_Sel = SLTU;
                    default: ALU_Sel = ADD;
                endcase
                result_src = 2'b00;
            end
            JAL: begin
                reg_write = 1'b1;
                alu_src = 1'b1;
                imm_sel = 3'b100;
                jump = 1'b1;
                result_src = 2'b10;
            end
            JALR: begin
                reg_write = 1'b1;
                alu_src = 1'b1;
                jump = 1'b1;
                jalr = 1'b1;
                result_src = 2'b10;
                imm_sel = 3'b000;
            end
            LUI, AUIPC: begin
                reg_write = 1'b1;
                alu_src = 1'b1;
                imm_sel = 3'b011;
                ALU_Sel = opcode[5] ? PASSB : ADD;
            end
            FENCE: begin
                reg_write = 1'b0;
                alu_src = 1'b0;
                mem_write = 1'b0;
                mem_read = 1'b0;
                branch = 1'b0;
                jump = 1'b0;
                jalr = 1'b0;
                result_src = 2'b00;
                ALU_Sel = ADD;
            end
        endcase
    end
endmodule
