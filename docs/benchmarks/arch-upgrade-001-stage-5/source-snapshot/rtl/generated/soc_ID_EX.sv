import pipeline_pkg::*;

module soc_ID_EX(
    input logic enable,
    input logic clk, rst, stall, flush,
    input logic [4:0] rs1addr_ID, rs2addr_ID,
    input logic valid_ID,
    input logic [31:0] pc_ID, rs1out, rs2out, imm_out, instruction_ID,
    input ctrl_t ctrl_ID,
    output logic valid_EX,
    output logic [31:0] pc_EX, rs1_EX, rs2_EX, imm_EX, instruction_EX,
    output logic [4:0] rs1addr_EX, rs2addr_EX, 
    output ctrl_t ctrl_EX
);
    always_ff @(posedge clk) begin
        if (rst || enable) begin
        if (rst) begin
            valid_EX <= 1'b0;
            pc_EX <= 32'b0;
            rs1_EX <= 32'b0;
            rs2_EX <= 32'b0;
            imm_EX <= 32'b0;
            instruction_EX <= 32'h00000013;
            rs1addr_EX <= 5'd0;
            rs2addr_EX <= 5'd0;
            ctrl_EX <= '0;
        end else if (stall || flush) begin
            valid_EX <= 1'b0;
            pc_EX <= 32'b0;
            rs1_EX <= 32'b0;
            rs2_EX <= 32'b0;
            imm_EX <= 32'b0;
            instruction_EX <= 32'h00000013;
            rs1addr_EX <= 5'd0;
            rs2addr_EX <= 5'd0;
            ctrl_EX <= '0;
        end else begin
            valid_EX <= valid_ID;
            pc_EX <= pc_ID;
            rs1_EX <= rs1out;
            rs2_EX <= rs2out;
            imm_EX <= imm_out;
            instruction_EX <= instruction_ID;
            rs1addr_EX <= rs1addr_ID;
            rs2addr_EX <= rs2addr_ID;
            ctrl_EX <= ctrl_ID;
        end
        end
    end
endmodule
