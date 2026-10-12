module PC_IF(
    input logic clk, rst,
    input logic [31:0] pc_target,
    input logic pc_src,
    input logic stall,
    output logic [31:0] pc
);
    logic [31:0] pc_plus4, pc_next;
    assign pc_plus4 = pc + 32'd4;
    assign pc_next = pc_src ? pc_target : pc_plus4;
    
    always_ff @(posedge clk) begin
        if (rst) pc <= 32'b0;
        else if (!stall) pc <= pc_next;
    end
        
endmodule