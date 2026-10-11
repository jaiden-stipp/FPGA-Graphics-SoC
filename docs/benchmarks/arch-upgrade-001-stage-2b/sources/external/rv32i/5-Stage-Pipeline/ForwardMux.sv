module ForwardMux (
    input logic [1:0] forwardSel,
    input logic [31:0] reg_data_EX, ALU_result_MEM, wr_data,
    output logic [31:0] reg_data_forward
);
    always_comb begin
        case (forwardSel) 
            2'b00: reg_data_forward = reg_data_EX;
            2'b10: reg_data_forward = ALU_result_MEM;
            2'b01: reg_data_forward = wr_data;
            default: reg_data_forward = reg_data_EX;
        endcase
    end
endmodule