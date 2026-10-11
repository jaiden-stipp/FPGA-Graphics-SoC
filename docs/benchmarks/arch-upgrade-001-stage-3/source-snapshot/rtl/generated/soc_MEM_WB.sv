import pipeline_pkg::*;

module soc_MEM_WB(
    input logic enable,
    input logic clk, rst,
    input logic valid_MEM,
    input logic [31:0] ALU_result_MEM, rdata, pc_MEM, instruction_MEM, store_data_MEM,
    input ctrl_t ctrl_MEM,
    output logic valid_WB,
    output logic [31:0] ALU_result_WB, rdata_WB, pc_WB, instruction_WB, store_data_WB,
    output ctrl_t ctrl_WB
);
    always_ff @(posedge clk) begin
        if (rst || enable) begin
        if (rst) begin
            valid_WB <= 1'b0;
            ALU_result_WB <= 32'b0;
            rdata_WB <= 32'b0;
            pc_WB <= 32'b0;
            instruction_WB <= 32'h00000013;
            store_data_WB <= 32'b0;
            ctrl_WB <= '0;
        end else begin
            valid_WB <= valid_MEM;
            ALU_result_WB <= ALU_result_MEM;
            rdata_WB <= rdata;
            pc_WB <= pc_MEM;
            instruction_WB <= instruction_MEM;
            store_data_WB <= store_data_MEM;
            ctrl_WB <= ctrl_MEM;
        end
        end
    end
endmodule
