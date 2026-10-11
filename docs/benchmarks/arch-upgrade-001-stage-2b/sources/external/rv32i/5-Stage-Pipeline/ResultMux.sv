module ResultMux(
	input logic [1:0] result_src,
	input logic [31:0] ALU_result, mem_rdata, pc_plus4,
	output logic [31:0] wr_data
	
);
	always_comb case(result_src)
        2'b00: wr_data = ALU_result;
        2'b01: wr_data = mem_rdata;
        2'b10: wr_data = pc_plus4;
        default: wr_data = 32'b0;
   endcase
endmodule